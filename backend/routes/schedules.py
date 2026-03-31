import json
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter
from database import get_db
from models import ScheduleCreate, ScheduleUpdate, DEFAULT_PERMISSIONS
import cron as cron_parser

router = APIRouter(prefix="/api/schedules", tags=["schedules"])


def _parse_schedule_row(row):
    sched = dict(row)
    try:
        sched["permissions"] = json.loads(sched.get("permissions") or "{}")
    except (json.JSONDecodeError, TypeError):
        sched["permissions"] = DEFAULT_PERMISSIONS
    sched["enabled"] = bool(sched.get("enabled", 1))
    return sched


@router.get("")
async def list_schedules():
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM schedules ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [_parse_schedule_row(r) for r in rows]
    finally:
        await db.close()


@router.get("/{schedule_id}")
async def get_schedule(schedule_id: str):
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM schedules WHERE id = ?", (schedule_id,))
        row = await cursor.fetchone()
        if not row:
            return {"error": "not found"}, 404
        return _parse_schedule_row(row)
    finally:
        await db.close()


@router.post("")
async def create_schedule(body: ScheduleCreate):
    schedule_id = str(uuid.uuid4())
    permissions = body.permissions if body.permissions else DEFAULT_PERMISSIONS
    permissions_json = json.dumps(permissions)

    # Validate cron and compute initial next_run_at
    now = datetime.now(timezone.utc)
    next_run = cron_parser.next_run_after(body.cron_expression, now)
    next_run_str = next_run.strftime("%Y-%m-%dT%H:%M:%SZ")

    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO schedules (id, name, cron_expression, title_template, prompt, model, priority, work_dir, project_id, permissions, assistant_id, next_run_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                schedule_id, body.name, body.cron_expression, body.title_template,
                body.prompt, body.model, body.priority, body.work_dir,
                body.project_id, permissions_json, body.assistant_id, next_run_str,
            ),
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM schedules WHERE id = ?", (schedule_id,))
        return _parse_schedule_row(await cursor.fetchone())
    finally:
        await db.close()


@router.patch("/{schedule_id}")
async def update_schedule(schedule_id: str, body: ScheduleUpdate):
    db = await get_db()
    try:
        updates = []
        params = []
        data = body.model_dump(exclude_none=True)

        for field, value in data.items():
            if field == "permissions":
                updates.append(f"{field} = ?")
                params.append(json.dumps(value))
            elif field == "enabled":
                updates.append(f"{field} = ?")
                params.append(1 if value else 0)
            else:
                updates.append(f"{field} = ?")
                params.append(value)
        if not updates:
            return {"error": "no fields to update"}

        # Recompute next_run_at if cron changed
        if "cron_expression" in data:
            now = datetime.now(timezone.utc)
            next_run = cron_parser.next_run_after(data["cron_expression"], now)
            next_run_str = next_run.strftime("%Y-%m-%dT%H:%M:%SZ")
            updates.append("next_run_at = ?")
            params.append(next_run_str)

        updates.append("updated_at = datetime('now')")
        params.append(schedule_id)
        await db.execute(
            f"UPDATE schedules SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM schedules WHERE id = ?", (schedule_id,))
        return _parse_schedule_row(await cursor.fetchone())
    finally:
        await db.close()


@router.delete("/{schedule_id}")
async def delete_schedule(schedule_id: str):
    db = await get_db()
    try:
        await db.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
        await db.commit()
        return {"ok": True}
    finally:
        await db.close()


@router.post("/{schedule_id}/trigger")
async def trigger_schedule(schedule_id: str):
    """Manually trigger a schedule to create a job immediately."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM schedules WHERE id = ?", (schedule_id,))
        row = await cursor.fetchone()
        if not row:
            return {"error": "not found"}, 404
        sched = dict(row)

        now = datetime.now(timezone.utc)
        job_id = str(uuid.uuid4())

        run_count_cursor = await db.execute(
            "SELECT COUNT(*) FROM jobs WHERE schedule_id = ?", (schedule_id,)
        )
        run_count = (await run_count_cursor.fetchone())[0]
        title = sched["title_template"].replace(
            "{date}", now.strftime("%Y-%m-%d")
        ).replace("{n}", str(run_count + 1))

        await db.execute(
            """INSERT INTO jobs (id, title, prompt, model, priority, work_dir, project_id, permissions, assistant_id, schedule_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                job_id, title, sched["prompt"], sched["model"],
                sched["priority"], sched["work_dir"], sched["project_id"],
                sched["permissions"], sched["assistant_id"], schedule_id,
            ),
        )
        await db.execute(
            "UPDATE schedules SET last_run_at = ?, updated_at = datetime('now') WHERE id = ?",
            (now.strftime("%Y-%m-%dT%H:%M:%SZ"), schedule_id),
        )
        await db.commit()

        cursor = await db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        job = dict(await cursor.fetchone())
        try:
            job["permissions"] = json.loads(job.get("permissions") or "{}")
        except (json.JSONDecodeError, TypeError):
            job["permissions"] = DEFAULT_PERMISSIONS
        return job
    finally:
        await db.close()


@router.get("/{schedule_id}/history")
async def schedule_history(schedule_id: str):
    """Get jobs spawned by this schedule."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM jobs WHERE schedule_id = ? ORDER BY created_at DESC",
            (schedule_id,),
        )
        rows = await cursor.fetchall()
        results = []
        for r in rows:
            job = dict(r)
            try:
                job["permissions"] = json.loads(job.get("permissions") or "{}")
            except (json.JSONDecodeError, TypeError):
                job["permissions"] = DEFAULT_PERMISSIONS
            results.append(job)
        return results
    finally:
        await db.close()
