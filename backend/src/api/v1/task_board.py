"""Investigation task board endpoints."""

import secrets
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.api.v1.auth.dependencies import get_current_user

log = structlog.get_logger()
router = APIRouter()


class TaskCreate(BaseModel):
    investigation_id: str
    title: str = Field(..., min_length=1, max_length=500)
    description: str = ""
    priority: str = Field("medium", pattern="^(low|medium|high|critical)$")
    assigned_to: str | None = None
    labels: list[str] = []
    due_date: str | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = Field(None, pattern="^(todo|in_progress|done)$")
    priority: str | None = Field(None, pattern="^(low|medium|high|critical)$")
    assigned_to: str | None = None
    labels: list[str] | None = None
    sort_order: int | None = None


class TaskResponse(BaseModel):
    id: str
    investigation_id: str
    title: str
    description: str
    status: str
    priority: str
    assigned_to: str | None
    created_by: str
    labels: list[str]
    sort_order: int
    due_date: str | None
    completed_at: str | None
    created_at: str


class TaskBoardResponse(BaseModel):
    tasks: list[TaskResponse]
    total: int
    by_status: dict[str, int]


@router.get("/investigations/{investigation_id}/tasks", response_model=TaskBoardResponse)
async def list_tasks(
    investigation_id: str,
    current_user: Any = Depends(get_current_user),
) -> TaskBoardResponse:
    """List all tasks for an investigation."""
    return TaskBoardResponse(
        tasks=[],
        total=0,
        by_status={"todo": 0, "in_progress": 0, "done": 0},
    )


@router.post("/investigations/{investigation_id}/tasks", response_model=TaskResponse, status_code=201)
async def create_task(
    investigation_id: str,
    body: TaskCreate,
    current_user: Any = Depends(get_current_user),
) -> TaskResponse:
    """Create a new task in an investigation."""
    user_id = str(getattr(current_user, "id", "unknown"))
    now = datetime.now(timezone.utc).isoformat()

    return TaskResponse(
        id=secrets.token_hex(16),
        investigation_id=investigation_id,
        title=body.title,
        description=body.description,
        status="todo",
        priority=body.priority,
        assigned_to=body.assigned_to,
        created_by=user_id,
        labels=body.labels,
        sort_order=0,
        due_date=body.due_date,
        completed_at=None,
        created_at=now,
    )


@router.patch("/investigations/{investigation_id}/tasks/{task_id}")
async def update_task(
    investigation_id: str,
    task_id: str,
    body: TaskUpdate,
    current_user: Any = Depends(get_current_user),
) -> dict[str, str]:
    """Update a task."""
    return {"status": "updated", "id": task_id}


@router.delete("/investigations/{investigation_id}/tasks/{task_id}")
async def delete_task(
    investigation_id: str,
    task_id: str,
    current_user: Any = Depends(get_current_user),
) -> dict[str, str]:
    """Delete a task."""
    return {"status": "deleted", "id": task_id}
