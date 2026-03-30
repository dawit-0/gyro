from pydantic import BaseModel
from typing import Optional


class JobCreate(BaseModel):
    title: str
    prompt: str
    model: str = "claude-sonnet-4-20250514"
    priority: int = 0
    work_dir: str = ""
    project_id: Optional[str] = None


class JobUpdate(BaseModel):
    title: Optional[str] = None
    prompt: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[int] = None
    model: Optional[str] = None


class ProjectCreate(BaseModel):
    name: str
    description: str = ""


class AnswerCreate(BaseModel):
    answer: str
