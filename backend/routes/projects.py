import uuid
from fastapi import APIRouter
from database import get_db
from models import ProjectCreate

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("")
async def list_projects():
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM projects WHERE archived = 0 ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


@router.post("")
async def create_project(body: ProjectCreate):
    project_id = str(uuid.uuid4())
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO projects (id, name, description) VALUES (?, ?, ?)",
            (project_id, body.name, body.description),
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        return dict(await cursor.fetchone())
    finally:
        await db.close()


@router.delete("/{project_id}")
async def archive_project(project_id: str):
    db = await get_db()
    try:
        await db.execute(
            "UPDATE projects SET archived = 1 WHERE id = ?", (project_id,)
        )
        await db.commit()
        return {"ok": True}
    finally:
        await db.close()
