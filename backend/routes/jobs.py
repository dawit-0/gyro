import json
import uuid
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from database import get_db
from models import JobCreate, JobUpdate, DEFAULT_PERMISSIONS

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("")
async def list_jobs(project_id: str = None, status: str = None, parent_job_id: str = None):
    db = await get_db()
    try:
        query = "SELECT * FROM jobs WHERE 1=1"
        params = []
        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)
        if status:
            query += " AND status = ?"
            params.append(status)
        if parent_job_id:
            query += " AND parent_job_id = ?"
            params.append(parent_job_id)
        query += " ORDER BY created_at DESC"
        cursor = await db.execute(query, params)
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


@router.get("/{job_id}")
async def get_job(job_id: str):
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = await cursor.fetchone()
        if not row:
            return {"error": "not found"}, 404
        job = dict(row)
        try:
            job["permissions"] = json.loads(job.get("permissions") or "{}")
        except (json.JSONDecodeError, TypeError):
            job["permissions"] = DEFAULT_PERMISSIONS
        return job
    finally:
        await db.close()


async def _check_circular_dependency(db, job_id: str, parent_job_id: str) -> bool:
    """Return True if setting parent_job_id would create a cycle."""
    current = parent_job_id
    visited = {job_id}
    while current:
        if current in visited:
            return True
        visited.add(current)
        cursor = await db.execute("SELECT parent_job_id FROM jobs WHERE id = ?", (current,))
        row = await cursor.fetchone()
        if not row:
            break
        current = row["parent_job_id"]
    return False


@router.post("")
async def create_job(body: JobCreate):
    job_id = str(uuid.uuid4())
    permissions = body.permissions if body.permissions else DEFAULT_PERMISSIONS
    permissions_json = json.dumps(permissions)
    db = await get_db()
    try:
        # Validate parent job
        initial_status = "queued"
        if body.parent_job_id:
            if body.parent_job_id == job_id:
                return JSONResponse({"error": "job cannot be its own parent"}, status_code=400)
            cursor = await db.execute("SELECT id, status FROM jobs WHERE id = ?", (body.parent_job_id,))
            parent = await cursor.fetchone()
            if not parent:
                return JSONResponse({"error": "parent job not found"}, status_code=404)
            if await _check_circular_dependency(db, job_id, body.parent_job_id):
                return JSONResponse({"error": "circular dependency detected"}, status_code=400)
            if parent["status"] in ("failed", "cancelled"):
                initial_status = "cancelled"

        await db.execute(
            """INSERT INTO jobs (id, title, prompt, model, priority, work_dir, project_id, permissions, scheduled_for, parent_job_id, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (job_id, body.title, body.prompt, body.model, body.priority, body.work_dir, body.project_id, permissions_json, body.scheduled_for, body.parent_job_id, initial_status),
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = await cursor.fetchone()
        job = dict(row)
        job["permissions"] = json.loads(job["permissions"]) if job["permissions"] else DEFAULT_PERMISSIONS
        return job
    finally:
        await db.close()


@router.patch("/{job_id}")
async def update_job(job_id: str, body: JobUpdate):
    db = await get_db()
    try:
        updates = []
        params = []
        for field, value in body.model_dump(exclude_none=True).items():
            updates.append(f"{field} = ?")
            params.append(value)
        if not updates:
            return {"error": "no fields to update"}
        updates.append("updated_at = datetime('now')")
        params.append(job_id)
        await db.execute(
            f"UPDATE jobs SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        return dict(await cursor.fetchone())
    finally:
        await db.close()


@router.delete("/{job_id}")
async def delete_job(job_id: str):
    db = await get_db()
    try:
        # Unlink children so they become independent
        await db.execute("UPDATE jobs SET parent_job_id = NULL WHERE parent_job_id = ?", (job_id,))
        await db.execute("DELETE FROM agent_output WHERE agent_id IN (SELECT id FROM agents WHERE job_id = ?)", (job_id,))
        await db.execute("DELETE FROM agents WHERE job_id = ?", (job_id,))
        await db.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        await db.commit()
        return {"ok": True}
    finally:
        await db.close()


@router.get("/{job_id}/children")
async def get_job_children(job_id: str):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM jobs WHERE parent_job_id = ? ORDER BY created_at ASC",
            (job_id,),
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
