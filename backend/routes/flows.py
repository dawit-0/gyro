import uuid
from datetime import datetime, timezone
from fastapi import APIRouter
from database import get_db
from db import flows as db_flows, tasks as db_tasks, task_runs as db_task_runs
from db import task_run_output as db_output, task_dependencies as db_deps
from db import questions as db_questions
from models import FlowCreate, FlowUpdate
import cron as cron_parser

router = APIRouter(prefix="/api/flows", tags=["flows"])


@router.get("")
async def list_flows():
    db = await get_db()
    try:
        return await db_flows.list_active(db)
    finally:
        await db.close()


@router.get("/{flow_id}")
async def get_flow(flow_id: str):
    db = await get_db()
    try:
        flow = await db_flows.get_by_id(db, flow_id)
        if not flow:
            return {"error": "not found"}, 404
        return flow
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

        await db_flows.insert(db, flow_id, body.name, body.description,
                              body.schedule, next_run_at)
        await db.commit()
        return await db_flows.get_by_id(db, flow_id)
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

        await db_flows.update_fields(db, flow_id, updates, params)
        await db.commit()
        return await db_flows.get_by_id(db, flow_id)
    finally:
        await db.close()


@router.delete("/{flow_id}")
async def archive_flow(flow_id: str):
    db = await get_db()
    try:
        await db_task_runs.cancel_by_flow(db, flow_id)
        await db_questions.delete_by_flow(db, flow_id)
        await db_output.delete_by_flow(db, flow_id)
        await db_task_runs.delete_by_flow(db, flow_id)
        await db_deps.delete_by_flow(db, flow_id)
        await db_tasks.delete_by_flow(db, flow_id)
        await db_flows.clear_agent_flow_references(db, flow_id)
        await db_flows.archive(db, flow_id)
        await db.commit()
        return {"ok": True}
    finally:
        await db.close()


@router.post("/{flow_id}/retry")
async def retry_flow(flow_id: str):
    """Retry the entire flow from scratch — re-trigger all root tasks."""
    db = await get_db()
    try:
        flow = await db_flows.get_by_id(db, flow_id)
        if not flow:
            return {"error": "flow not found"}, 404

        # Cancel any running/queued runs first
        active_runs = await db_task_runs.get_active_by_flow(db, flow_id)
        for run_row in active_runs:
            await db_task_runs.cancel(db, run_row["id"])

        # Find root tasks and trigger them
        root_tasks = await db_tasks.get_root_tasks(db, flow_id)
        created_runs = []

        for task_row in root_tasks:
            task_id = task_row["id"]
            run_number = await db_task_runs.next_run_number(db, task_id)
            run_id = str(uuid.uuid4())

            await db_task_runs.insert(db, run_id, task_id, run_number,
                                      trigger="retry")
            created_runs.append({"id": run_id, "task_id": task_id, "run_number": run_number})

        await db.commit()
        return {"retried": len(created_runs), "runs": created_runs}
    finally:
        await db.close()


@router.post("/{flow_id}/resume")
async def resume_flow(flow_id: str):
    """Resume a flow from where it failed — retry the earliest failed tasks and let cascading handle the rest."""
    from main import orchestrator
    result = await orchestrator.resume_flow(flow_id)
    return result


@router.post("/{flow_id}/trigger")
async def trigger_flow(flow_id: str):
    """Manually trigger all root tasks (no upstream deps) in this flow."""
    db = await get_db()
    try:
        flow = await db_flows.get_by_id(db, flow_id)
        if not flow:
            return {"error": "flow not found"}, 404

        root_tasks = await db_tasks.get_root_tasks(db, flow_id)
        created_runs = []

        for task_row in root_tasks:
            task_id = task_row["id"]
            run_number = await db_task_runs.next_run_number(db, task_id)
            run_id = str(uuid.uuid4())

            await db_task_runs.insert(db, run_id, task_id, run_number,
                                      trigger="manual")
            created_runs.append({"id": run_id, "task_id": task_id, "run_number": run_number})

        await db.commit()
        return {"triggered": len(created_runs), "runs": created_runs}
    finally:
        await db.close()
