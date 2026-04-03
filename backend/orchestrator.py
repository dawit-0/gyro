import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

import aiosqlite

import cron as cron_parser
from database import get_db
from models import DEFAULT_PERMISSIONS

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
                await self._check_task_schedules()
                await self._check_flow_schedules()
                await self._dispatch_queued_runs()
            except Exception as e:
                print(f"[orchestrator] poll error: {e}")
            await asyncio.sleep(POLL_INTERVAL)

    async def _check_task_schedules(self):
        """Create task runs from due task-level schedules."""
        now = datetime.now(timezone.utc)
        now_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        db = await get_db()
        try:
            cursor = await db.execute(
                """SELECT * FROM tasks
                   WHERE status = 'active' AND schedule IS NOT NULL
                   AND schedule_enabled = 1 AND next_run_at IS NOT NULL
                   AND next_run_at <= ?""",
                (now_str,),
            )
            tasks = await cursor.fetchall()

            for task in tasks:
                task = dict(task)
                task_id = task["id"]

                # Get next run number
                cursor = await db.execute(
                    "SELECT COALESCE(MAX(run_number), 0) + 1 FROM task_runs WHERE task_id = ?",
                    (task_id,),
                )
                run_number = (await cursor.fetchone())[0]
                run_id = str(uuid.uuid4())

                await db.execute(
                    """INSERT INTO task_runs (id, task_id, run_number, trigger, status)
                       VALUES (?, ?, ?, 'schedule', 'queued')""",
                    (run_id, task_id, run_number),
                )

                # Advance next_run_at
                next_run = cron_parser.next_run_after(task["schedule"], now)
                next_run_str = next_run.strftime("%Y-%m-%dT%H:%M:%SZ")

                await db.execute(
                    "UPDATE tasks SET last_run_at = ?, next_run_at = ?, updated_at = datetime('now') WHERE id = ?",
                    (now_str, next_run_str, task_id),
                )
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
            cursor = await db.execute(
                """SELECT * FROM flows
                   WHERE archived = 0 AND schedule IS NOT NULL
                   AND schedule_enabled = 1 AND next_run_at IS NOT NULL
                   AND next_run_at <= ?""",
                (now_str,),
            )
            flows = await cursor.fetchall()

            for flow in flows:
                flow = dict(flow)
                flow_id = flow["id"]

                # Find root tasks (no upstream deps) in this flow
                cursor = await db.execute(
                    """SELECT id FROM tasks
                       WHERE flow_id = ? AND status = 'active'
                       AND NOT EXISTS (
                           SELECT 1 FROM task_dependencies td WHERE td.task_id = tasks.id
                       )""",
                    (flow_id,),
                )
                root_tasks = await cursor.fetchall()

                for task_row in root_tasks:
                    task_id = task_row["id"]
                    cursor = await db.execute(
                        "SELECT COALESCE(MAX(run_number), 0) + 1 FROM task_runs WHERE task_id = ?",
                        (task_id,),
                    )
                    run_number = (await cursor.fetchone())[0]
                    run_id = str(uuid.uuid4())

                    await db.execute(
                        """INSERT INTO task_runs (id, task_id, run_number, trigger, status)
                           VALUES (?, ?, ?, 'schedule', 'queued')""",
                        (run_id, task_id, run_number),
                    )

                    await self.sio.emit("task_run:started", {"id": run_id, "task_id": task_id, "trigger": "schedule"})

                # Advance next_run_at for the flow
                next_run = cron_parser.next_run_after(flow["schedule"], now)
                next_run_str = next_run.strftime("%Y-%m-%dT%H:%M:%SZ")

                await db.execute(
                    "UPDATE flows SET last_run_at = ?, next_run_at = ? WHERE id = ?",
                    (now_str, next_run_str, flow_id),
                )
                await db.commit()
        finally:
            await db.close()

    async def _dispatch_queued_runs(self):
        if len(self.running_processes) >= MAX_CONCURRENT_RUNS:
            return

        db = await get_db()
        try:
            slots = MAX_CONCURRENT_RUNS - len(self.running_processes)
            # Find queued runs where:
            # - task is active
            # - all upstream dependencies have a latest run with 'success' status (or no deps)
            cursor = await db.execute(
                """SELECT tr.*, t.prompt, t.model, t.work_dir, t.permissions, t.priority
                   FROM task_runs tr
                   JOIN tasks t ON t.id = tr.task_id
                   WHERE tr.status = 'queued' AND t.status = 'active'
                   AND NOT EXISTS (
                       SELECT 1 FROM task_dependencies td
                       WHERE td.task_id = tr.task_id
                       AND NOT EXISTS (
                           SELECT 1 FROM task_runs dep_run
                           WHERE dep_run.task_id = td.depends_on_task_id
                           AND dep_run.status = 'success'
                           AND dep_run.run_number = (
                               SELECT MAX(run_number) FROM task_runs WHERE task_id = td.depends_on_task_id
                           )
                       )
                   )
                   ORDER BY t.priority DESC, tr.started_at ASC LIMIT ?""",
                (slots,),
            )
            runs = await cursor.fetchall()

            for run in runs:
                await self._start_run(db, dict(run))
        finally:
            await db.close()

    async def _start_run(self, db: aiosqlite.Connection, run: dict):
        run_id = run["id"]
        task_id = run["task_id"]

        await db.execute(
            "UPDATE task_runs SET status = 'running', started_at = datetime('now') WHERE id = ?",
            (run_id,),
        )
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

    async def _execute_run(self, run_id: str, run: dict):
        task_id = run["task_id"]
        work_dir = run["work_dir"] or os.getcwd()
        model = run["model"] or "claude-sonnet-4-20250514"
        prompt = run["prompt"]
        start_time = datetime.now(timezone.utc)
        seq = 0

        try:
            permissions = json.loads(run.get("permissions") or "{}")
        except (json.JSONDecodeError, TypeError):
            permissions = DEFAULT_PERMISSIONS

        try:
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

            db = await get_db()
            try:
                await db.execute(
                    "UPDATE task_runs SET pid = ? WHERE id = ?",
                    (proc.pid, run_id),
                )
                await db.commit()
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
                        await db.execute(
                            "INSERT INTO task_run_output (task_run_id, seq, type, content) VALUES (?, ?, ?, ?)",
                            (run_id, seq, output_type, content),
                        )
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

            db = await get_db()
            try:
                await db.execute(
                    """UPDATE task_runs SET status = ?, exit_code = ?, duration_ms = ?,
                       num_turns = ?, finished_at = datetime('now'), error_message = ?
                       WHERE id = ?""",
                    (status, exit_code, elapsed, seq, stderr_data or None, run_id),
                )

                if status == "success":
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

        except Exception as e:
            elapsed = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            db = await get_db()
            try:
                await db.execute(
                    """UPDATE task_runs SET status = 'failed', duration_ms = ?,
                       finished_at = datetime('now'), error_message = ? WHERE id = ?""",
                    (elapsed, str(e), run_id),
                )
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
                "error_message": str(e),
            })
            await self.sio.emit("task:updated", {"id": task_id, "latest_run_status": "failed"})
        finally:
            self.running_processes.pop(run_id, None)

    async def _maybe_auto_retry(self, db: aiosqlite.Connection, failed_run_id: str, task_id: str) -> bool:
        """Check if the failed run should be auto-retried. Returns True if a retry was queued."""
        # Get task retry config
        cursor = await db.execute(
            "SELECT max_retries, retry_delay_seconds FROM tasks WHERE id = ?", (task_id,)
        )
        task = await cursor.fetchone()
        if not task or not task["max_retries"] or task["max_retries"] <= 0:
            return False

        # Get the current attempt number of the failed run
        cursor = await db.execute(
            "SELECT attempt_number FROM task_runs WHERE id = ?", (failed_run_id,)
        )
        run = await cursor.fetchone()
        attempt = run["attempt_number"] if run and run["attempt_number"] else 1

        if attempt >= task["max_retries"]:
            return False

        # Schedule a retry
        delay = task["retry_delay_seconds"] or 10
        asyncio.create_task(self._delayed_retry(task_id, failed_run_id, attempt + 1, delay))
        return True

    async def _delayed_retry(self, task_id: str, failed_run_id: str, attempt: int, delay: int):
        """Wait for delay then queue a retry run."""
        await asyncio.sleep(delay)
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT COALESCE(MAX(run_number), 0) + 1 FROM task_runs WHERE task_id = ?",
                (task_id,),
            )
            run_number = (await cursor.fetchone())[0]
            run_id = str(uuid.uuid4())

            await db.execute(
                """INSERT INTO task_runs (id, task_id, run_number, trigger, status, attempt_number, retry_of_run_id)
                   VALUES (?, ?, ?, 'retry', 'queued', ?, ?)""",
                (run_id, task_id, run_number, attempt, failed_run_id),
            )
            await db.commit()

            await self.sio.emit("task:updated", {"id": task_id, "latest_run_status": "queued"})
            await self.sio.emit("task_run:started", {"id": run_id, "task_id": task_id, "trigger": "retry"})
        finally:
            await db.close()

    async def retry_task_run(self, task_id: str):
        """Manually retry the latest failed run for a task, then cascade downstream."""
        db = await get_db()
        try:
            # Get the latest failed run
            cursor = await db.execute(
                "SELECT * FROM task_runs WHERE task_id = ? ORDER BY run_number DESC LIMIT 1",
                (task_id,),
            )
            last_run = await cursor.fetchone()

            cursor = await db.execute(
                "SELECT COALESCE(MAX(run_number), 0) + 1 FROM task_runs WHERE task_id = ?",
                (task_id,),
            )
            run_number = (await cursor.fetchone())[0]
            run_id = str(uuid.uuid4())

            retry_of = last_run["id"] if last_run else None
            attempt = (last_run["attempt_number"] + 1) if last_run and last_run["attempt_number"] else 1

            await db.execute(
                """INSERT INTO task_runs (id, task_id, run_number, trigger, status, attempt_number, retry_of_run_id)
                   VALUES (?, ?, ?, 'retry', 'queued', ?, ?)""",
                (run_id, task_id, run_number, attempt, retry_of),
            )
            await db.commit()

            await self.sio.emit("task:updated", {"id": task_id, "latest_run_status": "queued"})
            return {"id": run_id, "task_id": task_id, "run_number": run_number}
        finally:
            await db.close()

    async def resume_flow(self, flow_id: str):
        """Resume a flow by retrying all failed/cancelled leaf tasks (tasks whose failure stopped the flow)."""
        db = await get_db()
        try:
            # Find all tasks in this flow whose latest run is failed or cancelled
            cursor = await db.execute(
                """SELECT t.id FROM tasks t
                   JOIN task_runs tr ON tr.task_id = t.id AND tr.run_number = (
                       SELECT MAX(run_number) FROM task_runs WHERE task_id = t.id
                   )
                   WHERE t.flow_id = ? AND t.status = 'active'
                   AND tr.status IN ('failed', 'cancelled')
                   AND NOT EXISTS (
                       SELECT 1 FROM task_dependencies td
                       JOIN task_runs dep_run ON dep_run.task_id = td.depends_on_task_id
                       AND dep_run.run_number = (
                           SELECT MAX(run_number) FROM task_runs WHERE task_id = td.depends_on_task_id
                       )
                       WHERE td.task_id = t.id AND dep_run.status IN ('failed', 'cancelled')
                   )""",
                (flow_id,),
            )
            tasks_to_retry = await cursor.fetchall()
            created_runs = []

            for task_row in tasks_to_retry:
                task_id = task_row["id"]
                cursor = await db.execute(
                    "SELECT * FROM task_runs WHERE task_id = ? ORDER BY run_number DESC LIMIT 1",
                    (task_id,),
                )
                last_run = await cursor.fetchone()

                cursor = await db.execute(
                    "SELECT COALESCE(MAX(run_number), 0) + 1 FROM task_runs WHERE task_id = ?",
                    (task_id,),
                )
                run_number = (await cursor.fetchone())[0]
                run_id = str(uuid.uuid4())

                retry_of = last_run["id"] if last_run else None

                await db.execute(
                    """INSERT INTO task_runs (id, task_id, run_number, trigger, status, attempt_number, retry_of_run_id)
                       VALUES (?, ?, ?, 'retry', 'queued', 1, ?)""",
                    (run_id, task_id, run_number, retry_of),
                )
                created_runs.append({"id": run_id, "task_id": task_id, "run_number": run_number})
                await self.sio.emit("task:updated", {"id": task_id, "latest_run_status": "queued"})

            await db.commit()
            return {"retried": len(created_runs), "runs": created_runs}
        finally:
            await db.close()

    async def _cascade_trigger_downstream(self, db: aiosqlite.Connection, completed_task_id: str):
        """When a task run succeeds, check downstream tasks and queue runs if all deps are met."""
        cursor = await db.execute(
            "SELECT DISTINCT task_id FROM task_dependencies WHERE depends_on_task_id = ?",
            (completed_task_id,),
        )
        downstream_tasks = await cursor.fetchall()

        for row in downstream_tasks:
            downstream_id = row["task_id"]

            # Check task is active
            cursor = await db.execute(
                "SELECT status FROM tasks WHERE id = ?", (downstream_id,)
            )
            task = await cursor.fetchone()
            if not task or task["status"] != "active":
                continue

            # Check all upstream deps have a successful latest run
            cursor = await db.execute(
                """SELECT td.depends_on_task_id FROM task_dependencies td
                   WHERE td.task_id = ?
                   AND NOT EXISTS (
                       SELECT 1 FROM task_runs tr
                       WHERE tr.task_id = td.depends_on_task_id
                       AND tr.status = 'success'
                       AND tr.run_number = (
                           SELECT MAX(run_number) FROM task_runs WHERE task_id = td.depends_on_task_id
                       )
                   )""",
                (downstream_id,),
            )
            unmet_deps = await cursor.fetchall()
            if unmet_deps:
                continue

            # Check no queued/running run already exists for this task
            cursor = await db.execute(
                "SELECT id FROM task_runs WHERE task_id = ? AND status IN ('queued', 'running')",
                (downstream_id,),
            )
            if await cursor.fetchone():
                continue

            # All deps met — create a queued run
            cursor = await db.execute(
                "SELECT COALESCE(MAX(run_number), 0) + 1 FROM task_runs WHERE task_id = ?",
                (downstream_id,),
            )
            run_number = (await cursor.fetchone())[0]
            run_id = str(uuid.uuid4())

            await db.execute(
                """INSERT INTO task_runs (id, task_id, run_number, trigger, status)
                   VALUES (?, ?, ?, 'dependency', 'queued')""",
                (run_id, downstream_id, run_number),
            )

            await self.sio.emit("task:updated", {"id": downstream_id, "latest_run_status": "queued"})

    async def _cascade_cancel_downstream(self, db: aiosqlite.Connection, failed_task_id: str):
        """Recursively cancel queued downstream runs when a task fails."""
        cursor = await db.execute(
            """SELECT DISTINCT tr.id, tr.task_id FROM task_runs tr
               JOIN task_dependencies td ON td.task_id = tr.task_id
               WHERE td.depends_on_task_id = ? AND tr.status = 'queued'""",
            (failed_task_id,),
        )
        queued_runs = await cursor.fetchall()

        for row in queued_runs:
            run_id = row["id"]
            task_id = row["task_id"]
            await db.execute(
                "UPDATE task_runs SET status = 'cancelled', finished_at = datetime('now') WHERE id = ?",
                (run_id,),
            )
            await self.sio.emit("task:updated", {"id": task_id, "latest_run_status": "cancelled"})
            await self.sio.emit("task_run:finished", {"id": run_id, "task_id": task_id, "status": "cancelled"})
            # Recurse
            await self._cascade_cancel_downstream(db, task_id)

    async def cancel_task_run(self, task_id: str):
        """Cancel the latest running/queued run for a task."""
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT id FROM task_runs WHERE task_id = ? AND status IN ('running', 'queued') ORDER BY run_number DESC LIMIT 1",
                (task_id,),
            )
            run = await cursor.fetchone()

            if run:
                run_id = run["id"]
                proc = self.running_processes.get(run_id)
                if proc:
                    try:
                        proc.terminate()
                    except ProcessLookupError:
                        pass
                    self.running_processes.pop(run_id, None)

                await db.execute(
                    "UPDATE task_runs SET status = 'cancelled', finished_at = datetime('now') WHERE id = ?",
                    (run_id,),
                )
                await self._cascade_cancel_downstream(db, task_id)
                await db.commit()

                await self.sio.emit("task_run:finished", {"id": run_id, "task_id": task_id, "status": "cancelled"})

            await self.sio.emit("task:updated", {"id": task_id, "latest_run_status": "cancelled"})
        finally:
            await db.close()
