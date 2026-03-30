from fastapi import APIRouter
from database import get_db

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("")
async def list_agents(job_id: str = None):
    db = await get_db()
    try:
        if job_id:
            cursor = await db.execute(
                "SELECT * FROM agents WHERE job_id = ? ORDER BY started_at DESC",
                (job_id,),
            )
        else:
            cursor = await db.execute("SELECT * FROM agents ORDER BY started_at DESC")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


@router.get("/{agent_id}")
async def get_agent(agent_id: str):
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
        row = await cursor.fetchone()
        if not row:
            return {"error": "not found"}, 404
        return dict(row)
    finally:
        await db.close()


@router.get("/{agent_id}/output")
async def get_agent_output(agent_id: str):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM agent_output WHERE agent_id = ? ORDER BY seq ASC",
            (agent_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()
