import json
import uuid
from fastapi import APIRouter
from database import get_db
from models import AssistantCreate, AssistantUpdate, SpawnJob, DEFAULT_PERMISSIONS

router = APIRouter(prefix="/api/assistants", tags=["assistants"])


def _parse_assistant_row(row):
    assistant = dict(row)
    try:
        assistant["context"] = json.loads(assistant.get("context") or "[]")
    except (json.JSONDecodeError, TypeError):
        assistant["context"] = []
    try:
        assistant["default_permissions"] = json.loads(assistant.get("default_permissions") or "{}")
    except (json.JSONDecodeError, TypeError):
        assistant["default_permissions"] = {}
    return assistant


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
async def list_assistants():
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM assistants ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [_parse_assistant_row(r) for r in rows]
    finally:
        await db.close()


@router.get("/{assistant_id}")
async def get_assistant(assistant_id: str):
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM assistants WHERE id = ?", (assistant_id,))
        row = await cursor.fetchone()
        if not row:
            return {"error": "not found"}, 404
        return _parse_assistant_row(row)
    finally:
        await db.close()


@router.post("")
async def create_assistant(body: AssistantCreate):
    assistant_id = str(uuid.uuid4())
    permissions = body.default_permissions if body.default_permissions else {}
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO assistants (id, name, description, instructions, context, default_model, default_permissions, default_work_dir, default_project_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                assistant_id,
                body.name,
                body.description,
                body.instructions,
                json.dumps(body.context),
                body.default_model,
                json.dumps(permissions),
                body.default_work_dir,
                body.default_project_id,
            ),
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM assistants WHERE id = ?", (assistant_id,))
        return _parse_assistant_row(await cursor.fetchone())
    finally:
        await db.close()


@router.patch("/{assistant_id}")
async def update_assistant(assistant_id: str, body: AssistantUpdate):
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
        params.append(assistant_id)
        await db.execute(
            f"UPDATE assistants SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM assistants WHERE id = ?", (assistant_id,))
        return _parse_assistant_row(await cursor.fetchone())
    finally:
        await db.close()


@router.delete("/{assistant_id}")
async def delete_assistant(assistant_id: str):
    db = await get_db()
    try:
        await db.execute("DELETE FROM assistants WHERE id = ?", (assistant_id,))
        await db.commit()
        return {"ok": True}
    finally:
        await db.close()


@router.post("/{assistant_id}/spawn")
async def spawn_job(assistant_id: str, body: SpawnJob):
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM assistants WHERE id = ?", (assistant_id,))
        row = await cursor.fetchone()
        if not row:
            return {"error": "assistant not found"}, 404
        assistant = _parse_assistant_row(row)

        # Build merged prompt
        parts = []
        if assistant["instructions"]:
            parts.append(assistant["instructions"])
        context_text = _format_context(assistant["context"])
        if context_text:
            parts.append("--- Context ---\n" + context_text)
        if body.prompt:
            parts.append("--- Task ---\n" + body.prompt)
        merged_prompt = "\n\n".join(parts)

        # Use assistant defaults, let user overrides take precedence
        model = body.model or assistant["default_model"]
        permissions = body.permissions if body.permissions else (assistant["default_permissions"] or DEFAULT_PERMISSIONS)
        work_dir = body.work_dir if body.work_dir is not None else assistant["default_work_dir"]
        project_id = body.project_id if body.project_id is not None else assistant["default_project_id"]

        job_id = str(uuid.uuid4())
        permissions_json = json.dumps(permissions)
        await db.execute(
            """INSERT INTO jobs (id, title, prompt, model, priority, work_dir, project_id, permissions, assistant_id, scheduled_for, parent_job_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (job_id, body.title, merged_prompt, model, body.priority, work_dir, project_id, permissions_json, assistant_id, body.scheduled_for, body.parent_job_id),
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        job = dict(await cursor.fetchone())
        job["permissions"] = json.loads(job["permissions"]) if job["permissions"] else DEFAULT_PERMISSIONS
        return job
    finally:
        await db.close()
