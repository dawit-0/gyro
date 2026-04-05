import os
import sys
import time

from fastapi import APIRouter

from database import get_db, DB_PATH

router = APIRouter(prefix="/api/debug", tags=["debug"])

_start_time = time.time()


@router.get("/status")
async def debug_status():
    # Import here to avoid circular imports — orchestrator is set after app creation
    from main import orchestrator

    # Orchestrator state
    poll_alive = (
        orchestrator._poll_task is not None
        and not orchestrator._poll_task.done()
    )
    active_run_ids = list(orchestrator.running_processes.keys())

    # DB queries
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM task_runs WHERE status = 'queued'"
        )
        queued_count = (await cursor.fetchone())[0]

        cursor = await db.execute(
            """SELECT tr.id as run_id, tr.task_id, tr.error_message, tr.finished_at
               FROM task_runs tr
               WHERE tr.status = 'failed'
               ORDER BY tr.finished_at DESC LIMIT 10"""
        )
        recent_failures = [dict(r) for r in await cursor.fetchall()]
    finally:
        await db.close()

    # System info
    db_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0

    return {
        "orchestrator": {
            "running": poll_alive,
            "active_runs": len(active_run_ids),
            "active_run_ids": active_run_ids,
            "max_concurrent": orchestrator._max_concurrent_runs,
            "poll_interval_seconds": 2,
        },
        "queued_runs": queued_count,
        "recent_failures": recent_failures,
        "system": {
            "python_version": sys.version.split()[0],
            "uptime_seconds": int(time.time() - _start_time),
            "db_size_bytes": db_size,
        },
    }
