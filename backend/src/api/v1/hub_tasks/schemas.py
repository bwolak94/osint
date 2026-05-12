"""Pydantic v2 schemas for the Hub productivity task management API."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class TaskStatus(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    DEFERRED = "deferred"
    CANCELLED = "cancelled"


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=512)
    description: str | None = None
    priority: int = Field(3, ge=1, le=5)
    due_at: datetime | None = None
    source: str = "user"


class TaskUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=512)
    description: str | None = None
    priority: int | None = Field(None, ge=1, le=5)
    status: TaskStatus | None = None
    due_at: datetime | None = None


class TaskResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    description: str | None
    priority: int
    status: str
    due_at: datetime | None
    source: str
    source_ref_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    tasks: list[TaskResponse]
    total: int
    skip: int
    limit: int


class StatusHistoryEntry(BaseModel):
    id: UUID
    old_status: str | None
    new_status: str
    changed_by: str
    changed_at: datetime

    model_config = {"from_attributes": True}


class AddDependencyRequest(BaseModel):
    depends_on_id: UUID
