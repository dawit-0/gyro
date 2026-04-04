import json
import uuid
from fastapi import APIRouter
from database import get_db
from models import AgentCreate, AgentUpdate, SpawnTask, DEFAULT_PERMISSIONS

router = APIRouter(prefix="/api/agents", tags=["agents"])


def _parse_agent_row(row):
    agent = dict(row)
    try:
        agent["context"] = json.loads(agent.get("context") or "[]")
    except (json.JSONDecodeError, TypeError):
        agent["context"] = []
    try:
        agent["default_permissions"] = json.loads(agent.get("default_permissions") or "{}")
    except (json.JSONDecodeError, TypeError):
        agent["default_permissions"] = {}
    return agent


def _format_context(context: list[dict]) -> str:
    parts = []
    for item in context:
        t = item.get("type", "")
        if t == "file":
            parts.append(f"[File: {item.get('path', '')}]")
        elif t == "url":
            parts.append(f"[Reference: {item.get('url', '')}]")
        elif t == "text":
            parts.append(item.get("content", ""))
    return "\n\n".join(parts)


@router.get("")
async def list_agents():
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM agents ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [_parse_agent_row(r) for r in rows]
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
        return _parse_agent_row(row)
    finally:
        await db.close()


@router.post("")
async def create_agent(body: AgentCreate):
    agent_id = str(uuid.uuid4())
    permissions = body.default_permissions if body.default_permissions else {}
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO agents (id, name, description, instructions, context, default_model, default_permissions, default_work_dir, default_flow_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                agent_id,
                body.name,
                body.description,
                body.instructions,
                json.dumps(body.context),
                body.default_model,
                json.dumps(permissions),
                body.default_work_dir,
                body.default_flow_id,
            ),
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
        return _parse_agent_row(await cursor.fetchone())
    finally:
        await db.close()


@router.patch("/{agent_id}")
async def update_agent(agent_id: str, body: AgentUpdate):
    db = await get_db()
    try:
        updates = []
        params = []
        for field, value in body.model_dump(exclude_none=True).items():
            updates.append(f"{field} = ?")
            if field in ("context", "default_permissions"):
                params.append(json.dumps(value))
            else:
                params.append(value)
        if not updates:
            return {"error": "no fields to update"}
        updates.append("updated_at = datetime('now')")
        params.append(agent_id)
        await db.execute(
            f"UPDATE agents SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
        return _parse_agent_row(await cursor.fetchone())
    finally:
        await db.close()


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str):
    db = await get_db()
    try:
        await db.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
        await db.commit()
        return {"ok": True}
    finally:
        await db.close()


@router.post("/{agent_id}/spawn")
async def spawn_task(agent_id: str, body: SpawnTask):
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
        row = await cursor.fetchone()
        if not row:
            return {"error": "agent not found"}, 404
        agent = _parse_agent_row(row)

        # Build merged prompt
        parts = []
        if agent["instructions"]:
            parts.append(agent["instructions"])
        context_text = _format_context(agent["context"])
        if context_text:
            parts.append("--- Context ---\n" + context_text)
        if body.prompt:
            parts.append("--- Task ---\n" + body.prompt)
        merged_prompt = "\n\n".join(parts)

        # Use agent defaults, let user overrides take precedence
        model = body.model or agent["default_model"]
        permissions = body.permissions if body.permissions else (agent["default_permissions"] or DEFAULT_PERMISSIONS)
        work_dir = body.work_dir if body.work_dir is not None else agent["default_work_dir"]
        flow_id = body.flow_id if body.flow_id is not None else agent["default_flow_id"]

        # Auto-create a flow if none provided
        if not flow_id:
            flow_id = str(uuid.uuid4())
            await db.execute(
                "INSERT INTO flows (id, name) VALUES (?, ?)",
                (flow_id, body.title),
            )

        task_id = str(uuid.uuid4())
        permissions_json = json.dumps(permissions)

        await db.execute(
            """INSERT INTO tasks (id, title, prompt, model, priority, work_dir, flow_id, permissions, agent_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (task_id, body.title, merged_prompt, model, body.priority, work_dir, flow_id, permissions_json, agent_id),
        )

        # Insert dependency rows
        depends_on = list(body.depends_on or [])
        for dep_id in depends_on:
            if dep_id != task_id:
                await db.execute(
                    "INSERT OR IGNORE INTO task_dependencies (task_id, depends_on_task_id) VALUES (?, ?)",
                    (task_id, dep_id),
                )

        # Optionally trigger a run immediately
        run = None
        if body.trigger:
            run_id = str(uuid.uuid4())
            await db.execute(
                """INSERT INTO task_runs (id, task_id, run_number, trigger, status)
                   VALUES (?, ?, 1, 'manual', 'queued')""",
                (run_id, task_id),
            )
            run = {"id": run_id, "task_id": task_id, "run_number": 1}

        await db.commit()
        cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        task_result = dict(await cursor.fetchone())
        try:
            task_result["permissions"] = json.loads(task_result.get("permissions") or "{}")
        except (json.JSONDecodeError, TypeError):
            task_result["permissions"] = DEFAULT_PERMISSIONS
        if run:
            task_result["triggered_run"] = run
        return task_result
    finally:
        await db.close()
