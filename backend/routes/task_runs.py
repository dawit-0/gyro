from fastapi import APIRouter
from database import get_db

router = APIRouter(prefix="/api/task-runs", tags=["task-runs"])


@router.get("")
async def list_task_runs(task_id: str = None):
    db = await get_db()
    try:
        if task_id:
            cursor = await db.execute(
                "SELECT * FROM task_runs WHERE task_id = ? ORDER BY started_at DESC",
                (task_id,),
            )
        else:
            cursor = await db.execute("SELECT * FROM task_runs ORDER BY started_at DESC")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


@router.get("/{run_id}")
async def get_task_run(run_id: str):
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM task_runs WHERE id = ?", (run_id,))
        row = await cursor.fetchone()
        if not row:
            return {"error": "not found"}, 404
        return dict(row)
    finally:
        await db.close()


@router.get("/{run_id}/output")
async def get_task_run_output(run_id: str):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM task_run_output WHERE task_run_id = ? ORDER BY seq ASC",
            (run_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()
