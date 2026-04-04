import asyncio
import json
import os
import traceback
import uuid
from datetime import datetime, timezone
from typing import Optional

import aiosqlite

import cron as cron_parser
from database import get_db
from db import tasks as db_tasks, task_runs as db_task_runs, flows as db_flows
from db import task_run_output as db_output, task_dependencies as db_deps
from db import task_xcom as db_xcom
from logging_config import get_logger, task_logger
from models import DEFAULT_PERMISSIONS

logger = get_logger("orchestrator")

MAX_CONCURRENT_RUNS = 5
POLL_INTERVAL = 2  # seconds


class Orchestrator:
    def __init__(self, sio):
        self.sio = sio
        self.running_processes: dict[str, asyncio.subprocess.Process] = {}
        self._poll_task: Optional[asyncio.Task] = None

    async def start(self):
        self._poll_task = asyncio.create_task(self._poll_loop())

    async def stop(self):
        if self._poll_task:
            self._poll_task.cancel()
        for run_id, proc in list(self.running_processes.items()):
            try:
                proc.terminate()
            except ProcessLookupError:
                pass
        self.running_processes.clear()

    async def _poll_loop(self):
        while True:
            try:
                logger.debug("poll cycle: %d active runs, %d slots available",
                             len(self.running_processes),
                             MAX_CONCURRENT_RUNS - len(self.running_processes))
                await self._check_task_schedules()
                await self._check_flow_schedules()
                await self._dispatch_queued_runs()
            except Exception:
                logger.exception("poll cycle error")
            await asyncio.sleep(POLL_INTERVAL)

    async def _check_task_schedules(self):
        """Create task runs from due task-level schedules."""
        now = datetime.now(timezone.utc)
        now_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        db = await get_db()
        try:
            tasks = await db_tasks.get_due_scheduled(db, now_str)

            for task in tasks:
                task_id = task["id"]
                run_number = await db_task_runs.next_run_number(db, task_id)
                run_id = str(uuid.uuid4())

                logger.info("schedule triggered task=%s", task_id)
                await db_task_runs.insert(db, run_id, task_id, run_number,
                                          trigger="schedule")

                # Advance next_run_at
                next_run = cron_parser.next_run_after(task["schedule"], now)
                next_run_str = next_run.strftime("%Y-%m-%dT%H:%M:%SZ")

                await db_tasks.update_schedule_times(db, task_id, now_str, next_run_str)
                await db.commit()

                await self.sio.emit("task:updated", {"id": task_id, "latest_run_status": "queued"})
                await self.sio.emit("task_run:started", {"id": run_id, "task_id": task_id, "trigger": "schedule"})
        finally:
            await db.close()

    async def _check_flow_schedules(self):
        """Create task runs for root tasks in flows with due schedules."""
        now = datetime.now(timezone.utc)
        now_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        db = await get_db()
        try:
            flows = await db_flows.get_due_scheduled(db, now_str)

            for flow in flows:
                flow_id = flow["id"]

                root_tasks = await db_tasks.get_root_tasks_alt(db, flow_id)

                logger.info("schedule triggered flow=%s, %d root tasks", flow_id, len(root_tasks))
                for task_row in root_tasks:
                    task_id = task_row["id"]
                    run_number = await db_task_runs.next_run_number(db, task_id)
                    run_id = str(uuid.uuid4())

                    await db_task_runs.insert(db, run_id, task_id, run_number,
                                              trigger="schedule")

                    await self.sio.emit("task_run:started", {"id": run_id, "task_id": task_id, "trigger": "schedule"})

                # Advance next_run_at for the flow
                next_run = cron_parser.next_run_after(flow["schedule"], now)
                next_run_str = next_run.strftime("%Y-%m-%dT%H:%M:%SZ")

                await db_flows.update_schedule_times(db, flow_id, now_str, next_run_str)
                await db.commit()
        finally:
            await db.close()

    async def _dispatch_queued_runs(self):
        if len(self.running_processes) >= MAX_CONCURRENT_RUNS:
            logger.debug("at capacity (%d running), skipping dispatch", MAX_CONCURRENT_RUNS)
            return

        db = await get_db()
        try:
            slots = MAX_CONCURRENT_RUNS - len(self.running_processes)
            runs = await db_task_runs.get_queued_ready(db, slots)

            if runs:
                logger.debug("dispatching %d queued runs", len(runs))
            for run in runs:
                await self._start_run(db, run)
        finally:
            await db.close()

    async def _start_run(self, db: aiosqlite.Connection, run: dict):
        run_id = run["id"]
        task_id = run["task_id"]

        logger.info("starting run=%s task=%s trigger=%s", run_id, task_id, run.get("trigger", "?"))

        await db_task_runs.set_running(db, run_id)
        await db.commit()

        await self.sio.emit("task:updated", {"id": task_id, "latest_run_status": "running"})
        await self.sio.emit("task_run:started", {"id": run_id, "task_id": task_id})

        asyncio.create_task(self._execute_run(run_id, run))

    def _build_allowed_tools(self, permissions: dict) -> list[str]:
        tools = []
        if permissions.get("file_read", True):
            tools.extend(["Read", "Glob", "Grep"])
        if permissions.get("file_write", False):
            tools.extend(["Edit", "Write"])
        if permissions.get("bash", False):
            tools.append("Bash")
        if permissions.get("web_search", False):
            tools.extend(["WebSearch", "WebFetch"])
        if permissions.get("mcp", False):
            tools.append("mcp__*")
        return tools

    async def _emit_event(self, db, run_id: str, task_id: str, seq: int, event_data: dict):
        """Insert a lifecycle event into task_run_output and emit via Socket.IO."""
        content = json.dumps(event_data)
        await db_output.insert(db, run_id, seq, "event", content)
        await db.commit()
        await self.sio.emit("task_run:output", {
            "task_run_id": run_id,
            "task_id": task_id,
            "seq": seq,
            "type": "event",
            "content": content,
        })

    async def _build_prompt_with_context(self, db, task_id: str, base_prompt: str) -> str:
        """Prepend upstream task outputs to the prompt for inter-task data passing."""
        upstream_deps = await db_deps.get_upstream_with_config(db, task_id)

        if not upstream_deps:
            return base_prompt

        context_sections = []
        for dep in upstream_deps:
            upstream_task_id = dep["depends_on_task_id"]
            pass_output = dep.get("pass_output", 1)
            max_chars = dep.get("max_output_chars", 4000)

            if not pass_output:
                continue

            latest_run = await db_task_runs.get_latest_successful(db, upstream_task_id)
            if not latest_run:
                continue

            upstream_task = await db_tasks.get_by_id(db, upstream_task_id)
            task_title = dict(upstream_task)["title"] if upstream_task else upstream_task_id[:8]

            result_text = await db_output.get_result_text(db, latest_run["id"], max_chars)
            if result_text.strip():
                context_sections.append(
                    f"=== Output from upstream task: {task_title} ===\n{result_text}"
                )

        if not context_sections:
            return base_prompt

        context_block = "\n\n".join(context_sections)
        return (
            f"The following context comes from upstream tasks that have already completed:\n\n"
            f"{context_block}\n\n"
            f"---\n\n"
            f"{base_prompt}"
        )

    async def _execute_run(self, run_id: str, run: dict):
        task_id = run["task_id"]
        work_dir = run["work_dir"] or os.getcwd()
        model = run["model"] or "claude-sonnet-4-20250514"
        base_prompt = run["prompt"]
        start_time = datetime.now(timezone.utc)
        seq = 0
        tlog = task_logger(run_id, task_id)

        try:
            permissions = json.loads(run.get("permissions") or "{}")
        except (json.JSONDecodeError, TypeError):
            permissions = DEFAULT_PERMISSIONS

        try:
            # Build prompt with upstream context (XCom-like data passing)
            db = await get_db()
            try:
                prompt = await self._build_prompt_with_context(db, task_id, base_prompt)
            finally:
                await db.close()

            cmd = [
                "claude",
                "--print",
                "--output-format", "stream-json",
                "--model", model,
            ]

            allowed_tools = self._build_allowed_tools(permissions)
            if allowed_tools:
                for tool in allowed_tools:
                    cmd.extend(["--allowedTools", tool])

            cmd.append(prompt)

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=work_dir,
            )
            self.running_processes[run_id] = proc
            tlog.info("subprocess started pid=%d", proc.pid)

            db = await get_db()
            try:
                await db_task_runs.set_pid(db, run_id, proc.pid)
                seq += 1
                await self._emit_event(db, run_id, task_id, seq,
                                        {"event": "subprocess_started", "pid": proc.pid})
            finally:
                await db.close()

            # Stream stdout
            assert proc.stdout is not None
            buffer = ""
            while True:
                chunk = await proc.stdout.read(4096)
                if not chunk:
                    break
                buffer += chunk.decode("utf-8", errors="replace")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue

                    seq += 1
                    content = line
                    output_type = "text"

                    try:
                        parsed = json.loads(line)
                        if isinstance(parsed, dict):
                            output_type = parsed.get("type", "text")
                            if "content" in parsed:
                                content = parsed["content"]
                            elif "result" in parsed:
                                content = parsed["result"]
                            else:
                                content = line
                    except json.JSONDecodeError:
                        pass

                    db = await get_db()
                    try:
                        await db_output.insert(db, run_id, seq, output_type, content)
                        await db.commit()
                    finally:
                        await db.close()

                    await self.sio.emit("task_run:output", {
                        "task_run_id": run_id,
                        "task_id": task_id,
                        "seq": seq,
                        "type": output_type,
                        "content": content,
                    })

            await proc.wait()
            exit_code = proc.returncode

            stderr_data = ""
            if proc.stderr:
                stderr_bytes = await proc.stderr.read()
                stderr_data = stderr_bytes.decode("utf-8", errors="replace").strip()

            elapsed = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            status = "success" if exit_code == 0 else "failed"

            tlog.info("finished status=%s exit=%s duration=%dms", status, exit_code, elapsed)
            if stderr_data and status == "failed":
                tlog.warning("stderr: %s", stderr_data[:500])

            db = await get_db()
            try:
                seq += 1
                await self._emit_event(db, run_id, task_id, seq,
                                        {"event": "subprocess_exited", "exit_code": exit_code, "duration_ms": elapsed})

                await db_task_runs.set_finished(db, run_id, status,
                                                 exit_code=exit_code,
                                                 duration_ms=elapsed,
                                                 num_turns=seq,
                                                 error_message=stderr_data or None)

                if status == "success":
                    # Store result as xcom for downstream tasks
                    result_text = await db_output.get_result_text(db, run_id, max_chars=8000)
                    if result_text.strip():
                        await db_xcom.insert(db, run_id, task_id, "return_value", result_text)
                    await self._cascade_trigger_downstream(db, task_id)
                else:
                    # Check if auto-retry is configured
                    retried = await self._maybe_auto_retry(db, run_id, task_id)
                    if not retried:
                        await self._cascade_cancel_downstream(db, task_id)

                await db.commit()
            finally:
                await db.close()

            await self.sio.emit("task_run:finished", {
                "id": run_id,
                "task_id": task_id,
                "status": status,
                "exit_code": exit_code,
                "duration_ms": elapsed,
            })
            await self.sio.emit("task:updated", {"id": task_id, "latest_run_status": status})

        except Exception:
            elapsed = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            tlog.exception("run failed with exception after %dms", elapsed)
            error_msg = traceback.format_exc()
            db = await get_db()
            try:
                await db_task_runs.set_failed(db, run_id, elapsed, error_msg)
                retried = await self._maybe_auto_retry(db, run_id, task_id)
                if not retried:
                    await self._cascade_cancel_downstream(db, task_id)
                await db.commit()
            finally:
                await db.close()

            await self.sio.emit("task_run:finished", {
                "id": run_id,
                "task_id": task_id,
                "status": "failed",
                "error_message": error_msg,
            })
            await self.sio.emit("task:updated", {"id": task_id, "latest_run_status": "failed"})
        finally:
            self.running_processes.pop(run_id, None)

    async def _maybe_auto_retry(self, db: aiosqlite.Connection, failed_run_id: str, task_id: str) -> bool:
        """Check if the failed run should be auto-retried. Returns True if a retry was queued."""
        task = await db_tasks.get_retry_config(db, task_id)
        if not task or not task["max_retries"] or task["max_retries"] <= 0:
            return False

        run = await db_task_runs.get_attempt_number(db, failed_run_id)
        attempt = run["attempt_number"] if run and run["attempt_number"] else 1

        if attempt >= task["max_retries"]:
            logger.warning("run=%s task=%s exhausted retries (%d/%d)",
                           failed_run_id, task_id, attempt, task["max_retries"])
            return False

        # Schedule a retry
        delay = task["retry_delay_seconds"] or 10
        logger.info("scheduling retry attempt=%d for run=%s task=%s in %ds",
                     attempt + 1, failed_run_id, task_id, delay)
        asyncio.create_task(self._delayed_retry(task_id, failed_run_id, attempt + 1, delay))
        return True

    async def _delayed_retry(self, task_id: str, failed_run_id: str, attempt: int, delay: int):
        """Wait for delay then queue a retry run."""
        await asyncio.sleep(delay)
        db = await get_db()
        try:
            run_number = await db_task_runs.next_run_number(db, task_id)
            run_id = str(uuid.uuid4())

            await db_task_runs.insert(db, run_id, task_id, run_number,
                                      trigger="retry", attempt_number=attempt,
                                      retry_of_run_id=failed_run_id)
            await db.commit()

            await self.sio.emit("task:updated", {"id": task_id, "latest_run_status": "queued"})
            await self.sio.emit("task_run:started", {"id": run_id, "task_id": task_id, "trigger": "retry"})
        finally:
            await db.close()

    async def retry_task_run(self, task_id: str):
        """Manually retry the latest failed run for a task, then cascade downstream."""
        db = await get_db()
        try:
            last_run = await db_task_runs.get_latest(db, task_id)
            run_number = await db_task_runs.next_run_number(db, task_id)
            run_id = str(uuid.uuid4())

            retry_of = last_run["id"] if last_run else None
            attempt = (last_run["attempt_number"] + 1) if last_run and last_run["attempt_number"] else 1

            await db_task_runs.insert(db, run_id, task_id, run_number,
                                      trigger="retry", attempt_number=attempt,
                                      retry_of_run_id=retry_of)
            await db.commit()

            await self.sio.emit("task:updated", {"id": task_id, "latest_run_status": "queued"})
            return {"id": run_id, "task_id": task_id, "run_number": run_number}
        finally:
            await db.close()

    async def resume_flow(self, flow_id: str):
        """Resume a flow by retrying all failed/cancelled leaf tasks (tasks whose failure stopped the flow)."""
        db = await get_db()
        try:
            tasks_to_retry = await db_tasks.get_resumable_failed_tasks(db, flow_id)
            created_runs = []

            for task_row in tasks_to_retry:
                task_id = task_row["id"]
                last_run = await db_task_runs.get_latest(db, task_id)
                run_number = await db_task_runs.next_run_number(db, task_id)
                run_id = str(uuid.uuid4())

                retry_of = last_run["id"] if last_run else None

                await db_task_runs.insert(db, run_id, task_id, run_number,
                                          trigger="retry",
                                          retry_of_run_id=retry_of)
                created_runs.append({"id": run_id, "task_id": task_id, "run_number": run_number})
                await self.sio.emit("task:updated", {"id": task_id, "latest_run_status": "queued"})

            await db.commit()
            return {"retried": len(created_runs), "runs": created_runs}
        finally:
            await db.close()

    async def _cascade_trigger_downstream(self, db: aiosqlite.Connection, completed_task_id: str):
        """When a task run succeeds, check downstream tasks and queue runs if all deps are met."""
        downstream_tasks = await db_deps.get_downstream(db, completed_task_id)

        for row in downstream_tasks:
            downstream_id = row["task_id"]

            # Check task is active
            task = await db_tasks.get_by_id(db, downstream_id)
            if not task or dict(task).get("status") != "active":
                continue

            # Check all upstream deps have a successful latest run
            unmet_deps = await db_deps.get_unmet_upstream(db, downstream_id)
            if unmet_deps:
                logger.debug("task=%s has unmet deps, skipping cascade", downstream_id)
                continue

            # Check no queued/running run already exists for this task
            if await db_task_runs.has_active_run(db, downstream_id):
                continue

            # All deps met — create a queued run
            run_number = await db_task_runs.next_run_number(db, downstream_id)
            run_id = str(uuid.uuid4())

            logger.info("cascade: queuing downstream task=%s (triggered by task=%s)",
                        downstream_id, completed_task_id)
            await db_task_runs.insert(db, run_id, downstream_id, run_number,
                                      trigger="dependency")

            await self.sio.emit("task:updated", {"id": downstream_id, "latest_run_status": "queued"})

    async def _cascade_cancel_downstream(self, db: aiosqlite.Connection, failed_task_id: str):
        """Recursively cancel queued downstream runs when a task fails."""
        queued_runs = await db_deps.get_queued_downstream(db, failed_task_id)

        for row in queued_runs:
            run_id = row["id"]
            task_id = row["task_id"]
            logger.warning("cascade cancel: run=%s task=%s (upstream task=%s failed)",
                           run_id, task_id, failed_task_id)
            await db_task_runs.cancel(db, run_id)
            await self.sio.emit("task:updated", {"id": task_id, "latest_run_status": "cancelled"})
            await self.sio.emit("task_run:finished", {"id": run_id, "task_id": task_id, "status": "cancelled"})
            # Recurse
            await self._cascade_cancel_downstream(db, task_id)

    async def cancel_task_run(self, task_id: str):
        """Cancel the latest running/queued run for a task."""
        db = await get_db()
        try:
            run = await db_task_runs.get_active_run(db, task_id)

            if run:
                run_id = run["id"]
                proc = self.running_processes.get(run_id)
                if proc:
                    logger.info("cancelling task=%s run=%s pid=%s", task_id, run_id, proc.pid)
                    try:
                        proc.terminate()
                    except ProcessLookupError:
                        pass
                    self.running_processes.pop(run_id, None)
                else:
                    logger.info("cancelling task=%s run=%s (no active process)", task_id, run_id)

                await db_task_runs.cancel(db, run_id)
                await self._cascade_cancel_downstream(db, task_id)
                await db.commit()

                await self.sio.emit("task_run:finished", {"id": run_id, "task_id": task_id, "status": "cancelled"})

            await self.sio.emit("task:updated", {"id": task_id, "latest_run_status": "cancelled"})
        finally:
            await db.close()
