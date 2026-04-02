import json
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from database import get_db
from models import TaskCreate, TaskUpdate, TaskTrigger, DependencyAdd, DEFAULT_PERMISSIONS
import cron as cron_parser

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _parse_task_row(row):
    task = dict(row)
    try:
        task["permissions"] = json.loads(task.get("permissions") or "{}")
    except (json.JSONDecodeError, TypeError):
        task["permissions"] = DEFAULT_PERMISSIONS
    return task


@router.get("")
async def list_tasks(flow_id: str = None, status: str = None):
    db = await get_db()
    try:
        query = "SELECT * FROM tasks WHERE 1=1"
        params = []
        if flow_id:
            query += " AND flow_id = ?"
            params.append(flow_id)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC"
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [_parse_task_row(r) for r in rows]
    finally:
        await db.close()


# DAG endpoint — must be before /{task_id} to avoid path conflict
@router.get("/dag")
async def get_dag(flow_id: str = None):
    db = await get_db()
    try:
        if flow_id:
            cursor = await db.execute(
                """SELECT t.id, t.title, t.status, t.model, t.schedule, t.created_at, t.updated_at,
                          tr.status as latest_run_status, tr.run_number as latest_run_number
                   FROM tasks t
                   LEFT JOIN task_runs tr ON tr.task_id = t.id AND tr.run_number = (
                       SELECT MAX(run_number) FROM task_runs WHERE task_id = t.id
                   )
                   WHERE t.flow_id = ? ORDER BY t.created_at ASC""",
                (flow_id,),
            )
        else:
            cursor = await db.execute(
                """SELECT t.id, t.title, t.status, t.model, t.schedule, t.created_at, t.updated_at,
                          tr.status as latest_run_status, tr.run_number as latest_run_number
                   FROM tasks t
                   LEFT JOIN task_runs tr ON tr.task_id = t.id AND tr.run_number = (
                       SELECT MAX(run_number) FROM task_runs WHERE task_id = t.id
                   )
                   ORDER BY t.created_at ASC"""
            )
        nodes = [dict(r) for r in await cursor.fetchall()]
        node_ids = {n["id"] for n in nodes}

        if node_ids:
            placeholders = ",".join("?" for _ in node_ids)
            cursor = await db.execute(
                f"SELECT task_id, depends_on_task_id FROM task_dependencies WHERE task_id IN ({placeholders})",
                list(node_ids),
            )
            edges = [{"source": r["depends_on_task_id"], "target": r["task_id"]} for r in await cursor.fetchall()]
        else:
            edges = []

        return {"nodes": nodes, "edges": edges}
    finally:
        await db.close()


@router.get("/{task_id}")
async def get_task(task_id: str):
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = await cursor.fetchone()
        if not row:
            return JSONResponse({"error": "not found"}, status_code=404)
        task = _parse_task_row(row)

        # Include latest run info
        cursor = await db.execute(
            "SELECT * FROM task_runs WHERE task_id = ? ORDER BY run_number DESC LIMIT 1",
            (task_id,),
        )
        latest_run = await cursor.fetchone()
        task["latest_run"] = dict(latest_run) if latest_run else None

        return task
    finally:
        await db.close()


async def _check_circular_dependency(db, task_id: str, upstream_ids: list[str]) -> bool:
    visited = {task_id}
    queue = list(upstream_ids)
    while queue:
        current = queue.pop(0)
        if current in visited:
            return True
        visited.add(current)
        cursor = await db.execute(
            "SELECT depends_on_task_id FROM task_dependencies WHERE task_id = ?", (current,)
        )
        for row in await cursor.fetchall():
            queue.append(row["depends_on_task_id"])
    return False


async def _next_run_number(db, task_id: str) -> int:
    cursor = await db.execute(
        "SELECT COALESCE(MAX(run_number), 0) + 1 FROM task_runs WHERE task_id = ?",
        (task_id,),
    )
    row = await cursor.fetchone()
    return row[0]


@router.post("")
async def create_task(body: TaskCreate):
    task_id = str(uuid.uuid4())
    permissions = body.permissions if body.permissions else DEFAULT_PERMISSIONS
    permissions_json = json.dumps(permissions)
    db = await get_db()
    try:
        depends_on = list(body.depends_on or [])

        if depends_on:
            if task_id in depends_on:
                return JSONResponse({"error": "task cannot depend on itself"}, status_code=400)
            for dep_id in depends_on:
                cursor = await db.execute("SELECT id FROM tasks WHERE id = ?", (dep_id,))
                if not await cursor.fetchone():
                    return JSONResponse({"error": f"dependency task {dep_id} not found"}, status_code=404)
            if await _check_circular_dependency(db, task_id, depends_on):
                return JSONResponse({"error": "circular dependency detected"}, status_code=400)

        # Compute next_run_at if schedule provided
        next_run_at = None
        if body.schedule:
            now = datetime.now(timezone.utc)
            next_run = cron_parser.next_run_after(body.schedule, now)
            next_run_at = next_run.strftime("%Y-%m-%dT%H:%M:%SZ")

        await db.execute(
            """INSERT INTO tasks (id, title, prompt, model, priority, work_dir, flow_id,
                                  assistant_id, permissions, schedule, next_run_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (task_id, body.title, body.prompt, body.model, body.priority,
             body.work_dir, body.flow_id, body.assistant_id, permissions_json,
             body.schedule, next_run_at),
        )

        for dep_id in depends_on:
            if dep_id != task_id:
                await db.execute(
                    "INSERT OR IGNORE INTO task_dependencies (task_id, depends_on_task_id) VALUES (?, ?)",
                    (task_id, dep_id),
                )

        await db.commit()
        cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        return _parse_task_row(await cursor.fetchone())
    finally:
        await db.close()


@router.patch("/{task_id}")
async def update_task(task_id: str, body: TaskUpdate):
    db = await get_db()
    try:
        updates = []
        params = []
        data = body.model_dump(exclude_none=True)

        # Handle schedule_enabled as integer
        if "schedule_enabled" in data:
            data["schedule_enabled"] = 1 if data["schedule_enabled"] else 0

        # Handle permissions as JSON
        if "permissions" in data:
            data["permissions"] = json.dumps(data["permissions"])

        for field, value in data.items():
            updates.append(f"{field} = ?")
            params.append(value)

        if not updates:
            return JSONResponse({"error": "no fields to update"}, status_code=400)

        # Recompute next_run_at if schedule changed
        if "schedule" in data and data["schedule"]:
            now = datetime.now(timezone.utc)
            next_run = cron_parser.next_run_after(data["schedule"], now)
            updates.append("next_run_at = ?")
            params.append(next_run.strftime("%Y-%m-%dT%H:%M:%SZ"))

        updates.append("updated_at = datetime('now')")
        params.append(task_id)
        await db.execute(
            f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        return _parse_task_row(await cursor.fetchone())
    finally:
        await db.close()


@router.delete("/{task_id}")
async def delete_task(task_id: str):
    db = await get_db()
    try:
        await db.execute("DELETE FROM task_dependencies WHERE task_id = ? OR depends_on_task_id = ?", (task_id, task_id))
        await db.execute("DELETE FROM task_run_output WHERE task_run_id IN (SELECT id FROM task_runs WHERE task_id = ?)", (task_id,))
        await db.execute("DELETE FROM questions WHERE task_id = ?", (task_id,))
        await db.execute("DELETE FROM task_runs WHERE task_id = ?", (task_id,))
        await db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        await db.commit()
        return {"ok": True}
    finally:
        await db.close()


@router.post("/{task_id}/trigger")
async def trigger_task(task_id: str, body: TaskTrigger = None):
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        task = await cursor.fetchone()
        if not task:
            return JSONResponse({"error": "task not found"}, status_code=404)

        run_number = await _next_run_number(db, task_id)
        run_id = str(uuid.uuid4())

        await db.execute(
            """INSERT INTO task_runs (id, task_id, run_number, trigger, status)
               VALUES (?, ?, ?, 'manual', 'queued')""",
            (run_id, task_id, run_number),
        )
        await db.commit()

        cursor = await db.execute("SELECT * FROM task_runs WHERE id = ?", (run_id,))
        return dict(await cursor.fetchone())
    finally:
        await db.close()


@router.get("/{task_id}/runs")
async def list_task_runs(task_id: str):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM task_runs WHERE task_id = ? ORDER BY run_number DESC",
            (task_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


@router.get("/{task_id}/dependencies")
async def get_task_dependencies(task_id: str):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT depends_on_task_id FROM task_dependencies WHERE task_id = ?", (task_id,)
        )
        dep_ids = [r["depends_on_task_id"] for r in await cursor.fetchall()]
        return {"task_id": task_id, "depends_on": dep_ids}
    finally:
        await db.close()


@router.post("/{task_id}/dependencies")
async def add_task_dependencies(task_id: str, body: DependencyAdd):
    db = await get_db()
    try:
        cursor = await db.execute("SELECT id FROM tasks WHERE id = ?", (task_id,))
        if not await cursor.fetchone():
            return JSONResponse({"error": "task not found"}, status_code=404)

        for dep_id in body.depends_on:
            if dep_id == task_id:
                return JSONResponse({"error": "task cannot depend on itself"}, status_code=400)
            cursor = await db.execute("SELECT id FROM tasks WHERE id = ?", (dep_id,))
            if not await cursor.fetchone():
                return JSONResponse({"error": f"dependency task {dep_id} not found"}, status_code=404)

        if await _check_circular_dependency(db, task_id, body.depends_on):
            return JSONResponse({"error": "circular dependency detected"}, status_code=400)

        for dep_id in body.depends_on:
            await db.execute(
                "INSERT OR IGNORE INTO task_dependencies (task_id, depends_on_task_id) VALUES (?, ?)",
                (task_id, dep_id),
            )
        await db.commit()
        return {"ok": True}
    finally:
        await db.close()


@router.delete("/{task_id}/dependencies/{dep_id}")
async def remove_task_dependency(task_id: str, dep_id: str):
    db = await get_db()
    try:
        await db.execute(
            "DELETE FROM task_dependencies WHERE task_id = ? AND depends_on_task_id = ?",
            (task_id, dep_id),
        )
        await db.commit()
        return {"ok": True}
    finally:
        await db.close()
