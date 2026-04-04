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


class TaskCreate(BaseModel):
    title: str
    prompt: str
    model: str = "claude-sonnet-4-20250514"
    priority: int = 0
    work_dir: str = ""
    flow_id: Optional[str] = None
    permissions: Optional[dict] = None
    schedule: Optional[str] = None
    assistant_id: Optional[str] = None
    depends_on: Optional[list[str]] = None
    max_retries: int = 0
    retry_delay_seconds: int = 10
    trigger: bool = False


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    prompt: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[int] = None
    model: Optional[str] = None
    work_dir: Optional[str] = None
    flow_id: Optional[str] = None
    permissions: Optional[dict] = None
    schedule: Optional[str] = None
    schedule_enabled: Optional[bool] = None
    max_retries: Optional[int] = None
    retry_delay_seconds: Optional[int] = None


class TaskTrigger(BaseModel):
    prompt_override: Optional[str] = None


class DependencyAdd(BaseModel):
    depends_on: list[str]


class FlowCreate(BaseModel):
    name: str
    description: str = ""
    schedule: Optional[str] = None


class FlowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    schedule: Optional[str] = None
    schedule_enabled: Optional[bool] = None


class AssistantCreate(BaseModel):
    name: str
    description: str = ""
    instructions: str = ""
    context: list[dict] = []
    default_model: str = "claude-sonnet-4-20250514"
    default_permissions: Optional[dict] = None
    default_work_dir: str = ""
    default_flow_id: Optional[str] = None


class AssistantUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    instructions: Optional[str] = None
    context: Optional[list[dict]] = None
    default_model: Optional[str] = None
    default_permissions: Optional[dict] = None
    default_work_dir: Optional[str] = None
    default_flow_id: Optional[str] = None


class SpawnTask(BaseModel):
    title: str
    prompt: str = ""
    model: Optional[str] = None
    priority: int = 0
    work_dir: Optional[str] = None
    flow_id: Optional[str] = None
    permissions: Optional[dict] = None
    depends_on: Optional[list[str]] = None
    trigger: bool = True  # whether to immediately trigger a run


class QuickTaskCreate(BaseModel):
    title: str
    prompt: str
    model: str = "claude-sonnet-4-20250514"
    work_dir: str = ""
    permissions: Optional[dict] = None
    schedule: Optional[str] = None
    max_retries: int = 0
    retry_delay_seconds: int = 10
    trigger: bool = True


class AnswerCreate(BaseModel):
    answer: str
