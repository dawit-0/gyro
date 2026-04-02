import json
import uuid
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from database import get_db
from models import JobCreate, JobUpdate, DependencyAdd, DEFAULT_PERMISSIONS

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


# DAG endpoint — must be before /{job_id} to avoid path conflict
@router.get("/dag")
async def get_dag(project_id: str = None):
    db = await get_db()
    try:
        # Fetch nodes
        if project_id:
            cursor = await db.execute(
                "SELECT id, title, status, model, created_at, updated_at FROM jobs WHERE project_id = ? ORDER BY created_at ASC",
                (project_id,),
            )
        else:
            cursor = await db.execute(
                "SELECT id, title, status, model, created_at, updated_at FROM jobs ORDER BY created_at ASC"
            )
        nodes = [dict(r) for r in await cursor.fetchall()]
        node_ids = {n["id"] for n in nodes}

        # Fetch edges
        if node_ids:
            placeholders = ",".join("?" for _ in node_ids)
            cursor = await db.execute(
                f"SELECT job_id, depends_on_job_id FROM job_dependencies WHERE job_id IN ({placeholders})",
                list(node_ids),
            )
            edges = [{"source": r["depends_on_job_id"], "target": r["job_id"]} for r in await cursor.fetchall()]
        else:
            edges = []

        return {"nodes": nodes, "edges": edges}
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


async def _check_circular_dependency(db, job_id: str, upstream_ids: list[str]) -> bool:
    """Return True if adding upstream_ids as dependencies of job_id would create a cycle.
    Uses BFS walking upstream through job_dependencies."""
    visited = {job_id}
    queue = list(upstream_ids)
    while queue:
        current = queue.pop(0)
        if current in visited:
            return True
        visited.add(current)
        cursor = await db.execute(
            "SELECT depends_on_job_id FROM job_dependencies WHERE job_id = ?", (current,)
        )
        for row in await cursor.fetchall():
            queue.append(row["depends_on_job_id"])
    return False


async def _insert_dependencies(db, job_id: str, depends_on: list[str], initial_status: str) -> str:
    """Insert dependency rows and determine initial status. Returns updated initial_status."""
    for dep_id in depends_on:
        if dep_id == job_id:
            continue
        cursor = await db.execute("SELECT id, status FROM jobs WHERE id = ?", (dep_id,))
        dep = await cursor.fetchone()
        if not dep:
            continue
        if dep["status"] in ("failed", "cancelled"):
            initial_status = "cancelled"
        await db.execute(
            "INSERT OR IGNORE INTO job_dependencies (job_id, depends_on_job_id) VALUES (?, ?)",
            (job_id, dep_id),
        )
    return initial_status


@router.post("")
async def create_job(body: JobCreate):
    job_id = str(uuid.uuid4())
    permissions = body.permissions if body.permissions else DEFAULT_PERMISSIONS
    permissions_json = json.dumps(permissions)
    db = await get_db()
    try:
        # Resolve depends_on: merge parent_job_id into depends_on list
        depends_on = list(body.depends_on or [])
        if body.parent_job_id and body.parent_job_id not in depends_on:
            depends_on.append(body.parent_job_id)

        initial_status = "queued"

        if depends_on:
            # Validate no self-reference
            if job_id in depends_on:
                return JSONResponse({"error": "job cannot depend on itself"}, status_code=400)

            # Validate all deps exist
            for dep_id in depends_on:
                cursor = await db.execute("SELECT id FROM jobs WHERE id = ?", (dep_id,))
                if not await cursor.fetchone():
                    return JSONResponse({"error": f"dependency job {dep_id} not found"}, status_code=404)

            if await _check_circular_dependency(db, job_id, depends_on):
                return JSONResponse({"error": "circular dependency detected"}, status_code=400)

        # Keep parent_job_id for backward compat (first dep)
        parent_job_id = depends_on[0] if depends_on else body.parent_job_id

        await db.execute(
            """INSERT INTO jobs (id, title, prompt, model, priority, work_dir, project_id, permissions, scheduled_for, parent_job_id, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (job_id, body.title, body.prompt, body.model, body.priority, body.work_dir, body.project_id, permissions_json, body.scheduled_for, parent_job_id, initial_status),
        )

        # Insert dependency rows
        if depends_on:
            initial_status = await _insert_dependencies(db, job_id, depends_on, initial_status)
            if initial_status == "cancelled":
                await db.execute(
                    "UPDATE jobs SET status = 'cancelled' WHERE id = ?", (job_id,)
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
        # Clean up dependency edges
        await db.execute("DELETE FROM job_dependencies WHERE job_id = ? OR depends_on_job_id = ?", (job_id, job_id))
        # Unlink children so they become independent (backward compat)
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


# Dependency management endpoints

@router.get("/{job_id}/dependencies")
async def get_job_dependencies(job_id: str):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT depends_on_job_id FROM job_dependencies WHERE job_id = ?", (job_id,)
        )
        dep_ids = [r["depends_on_job_id"] for r in await cursor.fetchall()]
        return {"job_id": job_id, "depends_on": dep_ids}
    finally:
        await db.close()


@router.post("/{job_id}/dependencies")
async def add_job_dependencies(job_id: str, body: DependencyAdd):
    db = await get_db()
    try:
        # Validate job exists
        cursor = await db.execute("SELECT id FROM jobs WHERE id = ?", (job_id,))
        if not await cursor.fetchone():
            return JSONResponse({"error": "job not found"}, status_code=404)

        # Validate deps exist and no self-ref
        for dep_id in body.depends_on:
            if dep_id == job_id:
                return JSONResponse({"error": "job cannot depend on itself"}, status_code=400)
            cursor = await db.execute("SELECT id FROM jobs WHERE id = ?", (dep_id,))
            if not await cursor.fetchone():
                return JSONResponse({"error": f"dependency job {dep_id} not found"}, status_code=404)

        if await _check_circular_dependency(db, job_id, body.depends_on):
            return JSONResponse({"error": "circular dependency detected"}, status_code=400)

        for dep_id in body.depends_on:
            await db.execute(
                "INSERT OR IGNORE INTO job_dependencies (job_id, depends_on_job_id) VALUES (?, ?)",
                (job_id, dep_id),
            )
        await db.commit()
        return {"ok": True}
    finally:
        await db.close()


@router.delete("/{job_id}/dependencies/{dep_id}")
async def remove_job_dependency(job_id: str, dep_id: str):
    db = await get_db()
    try:
        await db.execute(
            "DELETE FROM job_dependencies WHERE job_id = ? AND depends_on_job_id = ?",
            (job_id, dep_id),
        )
        await db.commit()
        return {"ok": True}
    finally:
        await db.close()
