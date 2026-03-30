import asyncio
import json
import os
import signal
import uuid
from datetime import datetime, timezone
from typing import Optional

import aiosqlite

from database import get_db

MAX_CONCURRENT_AGENTS = 5
POLL_INTERVAL = 2  # seconds


class Orchestrator:
    def __init__(self, sio):
        self.sio = sio
        self.running_agents: dict[str, asyncio.subprocess.Process] = {}
        self._poll_task: Optional[asyncio.Task] = None

    async def start(self):
        self._poll_task = asyncio.create_task(self._poll_loop())

    async def stop(self):
        if self._poll_task:
            self._poll_task.cancel()
        for agent_id, proc in list(self.running_agents.items()):
            try:
                proc.terminate()
            except ProcessLookupError:
                pass
        self.running_agents.clear()

    async def _poll_loop(self):
        while True:
            try:
                await self._dispatch_queued_jobs()
            except Exception as e:
                print(f"[orchestrator] poll error: {e}")
            await asyncio.sleep(POLL_INTERVAL)

    async def _dispatch_queued_jobs(self):
        if len(self.running_agents) >= MAX_CONCURRENT_AGENTS:
            return

        db = await get_db()
        try:
            slots = MAX_CONCURRENT_AGENTS - len(self.running_agents)
            cursor = await db.execute(
                "SELECT * FROM jobs WHERE status = 'queued' ORDER BY priority DESC, created_at ASC LIMIT ?",
                (slots,),
            )
            jobs = await cursor.fetchall()

            for job in jobs:
                await self._start_agent(db, dict(job))
        finally:
            await db.close()

    async def _start_agent(self, db: aiosqlite.Connection, job: dict):
        agent_id = str(uuid.uuid4())
        job_id = job["id"]

        await db.execute(
            "UPDATE jobs SET status = 'running', updated_at = datetime('now') WHERE id = ?",
            (job_id,),
        )
        await db.execute(
            "INSERT INTO agents (id, job_id, status) VALUES (?, ?, 'running')",
            (agent_id, job_id),
        )
        await db.commit()

        await self.sio.emit("job:updated", {"id": job_id, "status": "running"})
        await self.sio.emit("agent:started", {"id": agent_id, "job_id": job_id})

        asyncio.create_task(self._run_agent(agent_id, job))

    async def _run_agent(self, agent_id: str, job: dict):
        job_id = job["id"]
        work_dir = job["work_dir"] or os.getcwd()
        model = job["model"] or "claude-sonnet-4-20250514"
        prompt = job["prompt"]
        start_time = datetime.now(timezone.utc)
        seq = 0

        try:
            cmd = [
                "claude",
                "--print",
                "--output-format", "stream-json",
                "--model", model,
                prompt,
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=work_dir,
            )
            self.running_agents[agent_id] = proc

            db = await get_db()
            try:
                await db.execute(
                    "UPDATE agents SET pid = ? WHERE id = ?",
                    (proc.pid, agent_id),
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
                # Process complete lines
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue

                    seq += 1
                    content = line
                    output_type = "text"

                    # Try to parse as JSON for stream-json format
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
                            "INSERT INTO agent_output (agent_id, seq, type, content) VALUES (?, ?, ?, ?)",
                            (agent_id, seq, output_type, content),
                        )
                        await db.commit()
                    finally:
                        await db.close()

                    await self.sio.emit("agent:output", {
                        "agent_id": agent_id,
                        "job_id": job_id,
                        "seq": seq,
                        "type": output_type,
                        "content": content,
                    })

            await proc.wait()
            exit_code = proc.returncode

            # Read any stderr
            stderr_data = ""
            if proc.stderr:
                stderr_bytes = await proc.stderr.read()
                stderr_data = stderr_bytes.decode("utf-8", errors="replace").strip()

            elapsed = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            status = "done" if exit_code == 0 else "failed"

            db = await get_db()
            try:
                await db.execute(
                    """UPDATE agents SET status = ?, exit_code = ?, duration_ms = ?,
                       num_turns = ?, finished_at = datetime('now'), error_message = ?
                       WHERE id = ?""",
                    (status, exit_code, elapsed, seq, stderr_data or None, agent_id),
                )
                await db.execute(
                    "UPDATE jobs SET status = ?, updated_at = datetime('now') WHERE id = ?",
                    (status, job_id),
                )
                await db.commit()
            finally:
                await db.close()

            await self.sio.emit("agent:finished", {
                "id": agent_id,
                "job_id": job_id,
                "status": status,
                "exit_code": exit_code,
                "duration_ms": elapsed,
            })
            await self.sio.emit("job:updated", {"id": job_id, "status": status})

        except Exception as e:
            elapsed = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            db = await get_db()
            try:
                await db.execute(
                    """UPDATE agents SET status = 'failed', duration_ms = ?,
                       finished_at = datetime('now'), error_message = ? WHERE id = ?""",
                    (elapsed, str(e), agent_id),
                )
                await db.execute(
                    "UPDATE jobs SET status = 'failed', updated_at = datetime('now') WHERE id = ?",
                    (job_id,),
                )
                await db.commit()
            finally:
                await db.close()

            await self.sio.emit("agent:finished", {
                "id": agent_id,
                "job_id": job_id,
                "status": "failed",
                "error_message": str(e),
            })
            await self.sio.emit("job:updated", {"id": job_id, "status": "failed"})
        finally:
            self.running_agents.pop(agent_id, None)

    async def cancel_job(self, job_id: str):
        db = await get_db()
        try:
            # Find running agent for this job
            cursor = await db.execute(
                "SELECT id FROM agents WHERE job_id = ? AND status = 'running'",
                (job_id,),
            )
            agent = await cursor.fetchone()

            if agent:
                agent_id = agent["id"]
                proc = self.running_agents.get(agent_id)
                if proc:
                    try:
                        proc.terminate()
                    except ProcessLookupError:
                        pass
                    self.running_agents.pop(agent_id, None)

                await db.execute(
                    "UPDATE agents SET status = 'cancelled', finished_at = datetime('now') WHERE id = ?",
                    (agent_id,),
                )

            await db.execute(
                "UPDATE jobs SET status = 'cancelled', updated_at = datetime('now') WHERE id = ?",
                (job_id,),
            )
            await db.commit()
        finally:
            await db.close()

        await self.sio.emit("job:updated", {"id": job_id, "status": "cancelled"})
