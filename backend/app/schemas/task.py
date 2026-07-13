# Pydantic schemas for task JSON payloads (API in/out)
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TaskBase(BaseModel):
    # Shared fields for create + response
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None


class TaskCreate(TaskBase):
    # Body for POST /api/tasks
    pass


class TaskUpdate(BaseModel):
    # Body for PUT /api/tasks/{id} — all fields optional (partial update)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    completed: bool | None = None


class TaskResponse(TaskBase):
    # What the API returns for a task (includes DB-generated fields)
    model_config = ConfigDict(from_attributes=True)

    id: int
    completed: bool
    user_id: int
    created_at: datetime
    updated_at: datetime
