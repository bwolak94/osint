"""FastAPI router for Hub productivity task management.

Prefix: /hub/productivity-tasks  (distinct from /hub/tasks/{task_id} agent status)

Endpoints:
  GET    /hub/productivity-tasks                      — paginated list
  POST   /hub/productivity-tasks                      — create
  GET    /hub/productivity-tasks/{task_id}             — detail
  PATCH  /hub/productivity-tasks/{task_id}             — partial update
  DELETE /hub/productivity-tasks/{task_id}             — soft delete (cancel)
  GET    /hub/productivity-tasks/{task_id}/history     — status history
  POST   /hub/productivity-tasks/{task_id}/deps        — add dependency
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.repositories.hub_task_repository import HubTaskRepository
from src.api.v1.auth.dependencies import get_current_user
from src.api.v1.hub_tasks.schemas import (
    AddDependencyRequest,
    StatusHistoryEntry,
    TaskCreate,
    TaskListResponse,
    TaskResponse,
    TaskUpdate,
)
from src.core.domain.entities.user import User
from src.dependencies import get_db

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/hub/productivity-tasks", tags=["hub-tasks"])


def _repo(db: AsyncSession) -> HubTaskRepository:
    return HubTaskRepository(db)


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    status_filter: str | None = Query(None, alias="status"),
    priority: int | None = Query(None, ge=1, le=5),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: Annotated[User, Depends(get_current_user)] = ...,
    db: AsyncSession = Depends(get_db),
) -> TaskListResponse:
    """Return a paginated list of the authenticated user's productivity tasks."""
    repo = _repo(db)
    tasks = await repo.list_tasks(
        user_id=str(current_user.id),
        status=status_filter,
        priority=priority,
        skip=skip,
        limit=limit,
    )
    return TaskListResponse(
        tasks=[TaskResponse.model_validate(t) for t in tasks],
        total=len(tasks),
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    body: TaskCreate,
    current_user: Annotated[User, Depends(get_current_user)] = ...,
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """Create a new productivity task for the authenticated user."""
    repo = _repo(db)
    task = await repo.create_task(
        user_id=str(current_user.id),
        data=body.model_dump(),
    )
    return TaskResponse.model_validate(task)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)] = ...,
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """Return a single task owned by the authenticated user."""
    repo = _repo(db)
    task = await repo.get_task(user_id=str(current_user.id), task_id=str(task_id))
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return TaskResponse.model_validate(task)


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: UUID,
    body: TaskUpdate,
    current_user: Annotated[User, Depends(get_current_user)] = ...,
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """Partially update a task owned by the authenticated user."""
    repo = _repo(db)
    data = body.model_dump(exclude_none=True)
    task = await repo.update_task(
        user_id=str(current_user.id),
        task_id=str(task_id),
        data=data,
    )
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return TaskResponse.model_validate(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def cancel_task(
    task_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)] = ...,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-delete (cancel) a task. The task is preserved in history."""
    repo = _repo(db)
    cancelled = await repo.cancel_task(
        user_id=str(current_user.id),
        task_id=str(task_id),
        changed_by=str(current_user.id),
    )
    if not cancelled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")


@router.get("/{task_id}/history", response_model=list[StatusHistoryEntry])
async def get_task_history(
    task_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)] = ...,
    db: AsyncSession = Depends(get_db),
) -> list[StatusHistoryEntry]:
    """Return the full status change history for a task."""
    repo = _repo(db)
    # Verify ownership first
    task = await repo.get_task(user_id=str(current_user.id), task_id=str(task_id))
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    history = await repo.get_history(task_id=str(task_id))
    return [StatusHistoryEntry.model_validate(h) for h in history]


@router.post("/{task_id}/deps", status_code=status.HTTP_201_CREATED)
async def add_dependency(
    task_id: UUID,
    body: AddDependencyRequest,
    current_user: Annotated[User, Depends(get_current_user)] = ...,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Add a prerequisite dependency to a task."""
    repo = _repo(db)
    # Verify ownership of the dependent task
    task = await repo.get_task(user_id=str(current_user.id), task_id=str(task_id))
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    added = await repo.add_dependency(
        task_id=str(task_id),
        depends_on_id=str(body.depends_on_id),
    )
    if not added:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Dependency already exists",
        )
    return {"status": "created"}
