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
    scheduled_for: Optional[str] = None


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


class AssistantCreate(BaseModel):
    name: str
    description: str = ""
    instructions: str = ""
    context: list[dict] = []
    default_model: str = "claude-sonnet-4-20250514"
    default_permissions: Optional[dict] = None
    default_work_dir: str = ""
    default_project_id: Optional[str] = None


class AssistantUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    instructions: Optional[str] = None
    context: Optional[list[dict]] = None
    default_model: Optional[str] = None
    default_permissions: Optional[dict] = None
    default_work_dir: Optional[str] = None
    default_project_id: Optional[str] = None


class SpawnJob(BaseModel):
    title: str
    prompt: str = ""
    model: Optional[str] = None
    priority: int = 0
    work_dir: Optional[str] = None
    project_id: Optional[str] = None
    permissions: Optional[dict] = None
    scheduled_for: Optional[str] = None


class ScheduleCreate(BaseModel):
    name: str
    cron_expression: str
    title_template: str
    prompt: str
    model: str = "claude-sonnet-4-20250514"
    priority: int = 0
    work_dir: str = ""
    project_id: Optional[str] = None
    permissions: Optional[dict] = None
    assistant_id: Optional[str] = None


class ScheduleUpdate(BaseModel):
    name: Optional[str] = None
    cron_expression: Optional[str] = None
    title_template: Optional[str] = None
    prompt: Optional[str] = None
    model: Optional[str] = None
    priority: Optional[int] = None
    work_dir: Optional[str] = None
    project_id: Optional[str] = None
    permissions: Optional[dict] = None
    assistant_id: Optional[str] = None
    enabled: Optional[bool] = None
