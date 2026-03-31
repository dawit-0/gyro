from pydantic import BaseModel
from typing import Optional


PERMISSION_PRESETS = {
    "read-only": {
        "preset": "read-only",
        "file_read": True,
        "file_write": False,
        "bash": False,
        "web_search": False,
        "mcp": False,
    },
    "standard": {
        "preset": "standard",
        "file_read": True,
        "file_write": True,
        "bash": True,
        "web_search": False,
        "mcp": False,
    },
    "full": {
        "preset": "full",
        "file_read": True,
        "file_write": True,
        "bash": True,
        "web_search": True,
        "mcp": True,
    },
}

DEFAULT_PERMISSIONS = PERMISSION_PRESETS["standard"]


class JobCreate(BaseModel):
    title: str
    prompt: str
    model: str = "claude-sonnet-4-20250514"
    priority: int = 0
    work_dir: str = ""
    project_id: Optional[str] = None
    permissions: Optional[dict] = None


class JobUpdate(BaseModel):
    title: Optional[str] = None
    prompt: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[int] = None
    model: Optional[str] = None
    permissions: Optional[dict] = None


class ProjectCreate(BaseModel):
    name: str
    description: str = ""


class AnswerCreate(BaseModel):
    answer: str
