import json
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter
from database import get_db
from models import FlowCreate, FlowUpdate
import cron as cron_parser

router = APIRouter(prefix="/api/flows", tags=["flows"])


@router.get("")
async def list_flows():
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM flows WHERE archived = 0 ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


@router.get("/{flow_id}")
async def get_flow(flow_id: str):
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM flows WHERE id = ?", (flow_id,))
        row = await cursor.fetchone()
        if not row:
            return {"error": "not found"}, 404
        return dict(row)
    finally:
        await db.close()


@router.post("")
async def create_flow(body: FlowCreate):
    flow_id = str(uuid.uuid4())
    db = await get_db()
    try:
        next_run_at = None
        if body.schedule:
            now = datetime.now(timezone.utc)
            next_run = cron_parser.next_run_after(body.schedule, now)
            next_run_at = next_run.strftime("%Y-%m-%dT%H:%M:%SZ")

        await db.execute(
            "INSERT INTO flows (id, name, description, schedule, next_run_at) VALUES (?, ?, ?, ?, ?)",
            (flow_id, body.name, body.description, body.schedule, next_run_at),
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM flows WHERE id = ?", (flow_id,))
        return dict(await cursor.fetchone())
    finally:
        await db.close()


@router.patch("/{flow_id}")
async def update_flow(flow_id: str, body: FlowUpdate):
    db = await get_db()
    try:
        updates = []
        params = []
        data = body.model_dump(exclude_none=True)

        if "schedule_enabled" in data:
            data["schedule_enabled"] = 1 if data["schedule_enabled"] else 0

        for field, value in data.items():
            updates.append(f"{field} = ?")
            params.append(value)

        if not updates:
            return {"error": "no fields to update"}

        # Recompute next_run_at if schedule changed
        if "schedule" in data and data["schedule"]:
            now = datetime.now(timezone.utc)
            next_run = cron_parser.next_run_after(data["schedule"], now)
            updates.append("next_run_at = ?")
            params.append(next_run.strftime("%Y-%m-%dT%H:%M:%SZ"))

        params.append(flow_id)
        await db.execute(
            f"UPDATE flows SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM flows WHERE id = ?", (flow_id,))
        return dict(await cursor.fetchone())
    finally:
        await db.close()


@router.delete("/{flow_id}")
async def archive_flow(flow_id: str):
    db = await get_db()
    try:
        await db.execute(
            "UPDATE flows SET archived = 1 WHERE id = ?", (flow_id,)
        )
        await db.commit()
        return {"ok": True}
    finally:
        await db.close()


@router.post("/{flow_id}/trigger")
async def trigger_flow(flow_id: str):
    """Manually trigger all root tasks (no upstream deps) in this flow."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM flows WHERE id = ?", (flow_id,))
        flow = await cursor.fetchone()
        if not flow:
            return {"error": "flow not found"}, 404

        # Find root tasks: tasks in this flow with no upstream dependencies
        cursor = await db.execute(
            """SELECT t.id FROM tasks t
               WHERE t.flow_id = ? AND t.status = 'active'
               AND NOT EXISTS (
                   SELECT 1 FROM task_dependencies td WHERE td.task_id = t.id
               )""",
            (flow_id,),
        )
        root_tasks = await cursor.fetchall()
        created_runs = []

        for task_row in root_tasks:
            task_id = task_row["id"]
            # Get next run number
            cursor = await db.execute(
                "SELECT COALESCE(MAX(run_number), 0) + 1 FROM task_runs WHERE task_id = ?",
                (task_id,),
            )
            run_number = (await cursor.fetchone())[0]
            run_id = str(uuid.uuid4())

            await db.execute(
                """INSERT INTO task_runs (id, task_id, run_number, trigger, status)
                   VALUES (?, ?, ?, 'manual', 'queued')""",
                (run_id, task_id, run_number),
            )
            created_runs.append({"id": run_id, "task_id": task_id, "run_number": run_number})

        await db.commit()
        return {"triggered": len(created_runs), "runs": created_runs}
    finally:
        await db.close()
