"""Async repository for Hub productivity tasks.

Follows the same layered adapter pattern used throughout this project:
  Router → Repository (this layer) → SQLAlchemy AsyncSession

All write operations append a TaskStatusHistoryModel record so that every
status transition is auditable.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.hub_task import (
    TaskDependencyModel,
    TaskModel,
    TaskStatusHistoryModel,
)

log = structlog.get_logger(__name__)


class HubTaskRepository:
    """SQLAlchemy 2.0 async repository for productivity tasks."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Queries ──────────────────────────────────────────────────────────────

    async def list_tasks(
        self,
        user_id: str,
        status: str | None = None,
        priority: int | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[TaskModel]:
        """Return paginated tasks for a user, with optional filters."""
        stmt = select(TaskModel).where(
            TaskModel.user_id == uuid.UUID(user_id)
        )
        if status is not None:
            stmt = stmt.where(TaskModel.status == status)
        if priority is not None:
            stmt = stmt.where(TaskModel.priority == priority)
        stmt = stmt.order_by(TaskModel.created_at.desc()).offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_task(self, user_id: str, task_id: str) -> TaskModel | None:
        """Return a single task owned by the user, or None."""
        stmt = select(TaskModel).where(
            TaskModel.id == uuid.UUID(task_id),
            TaskModel.user_id == uuid.UUID(user_id),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_history(self, task_id: str) -> list[TaskStatusHistoryModel]:
        """Return all status history entries for a task, oldest first."""
        stmt = (
            select(TaskStatusHistoryModel)
            .where(TaskStatusHistoryModel.task_id == uuid.UUID(task_id))
            .order_by(TaskStatusHistoryModel.changed_at.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    # ── Commands ─────────────────────────────────────────────────────────────

    async def create_task(self, user_id: str, data: dict[str, Any]) -> TaskModel:
        """Persist a new task and record initial status in history."""
        task = TaskModel(
            user_id=uuid.UUID(user_id),
            title=data["title"],
            description=data.get("description"),
            priority=data.get("priority", 3),
            status=data.get("status", "todo"),
            due_at=data.get("due_at"),
            source=data.get("source", "user"),
            source_ref_id=uuid.UUID(data["source_ref_id"]) if data.get("source_ref_id") else None,
        )
        self._session.add(task)
        await self._session.flush()  # get the generated id

        history = TaskStatusHistoryModel(
            task_id=task.id,
            old_status=None,
            new_status=task.status,
            changed_by=data.get("changed_by", "user"),
        )
        self._session.add(history)
        await self._session.flush()

        await log.ainfo("hub_task_created", task_id=str(task.id), user_id=user_id)
        return task

    async def update_task(
        self,
        user_id: str,
        task_id: str,
        data: dict[str, Any],
    ) -> TaskModel | None:
        """Apply a partial update to a task; records status history on status change."""
        task = await self.get_task(user_id, task_id)
        if task is None:
            return None

        old_status = task.status

        allowed_fields = {"title", "description", "priority", "status", "due_at", "source"}
        for field in allowed_fields:
            if field in data and data[field] is not None:
                setattr(task, field, data[field])

        task.updated_at = datetime.now(timezone.utc)

        new_status = task.status
        if new_status != old_status:
            history = TaskStatusHistoryModel(
                task_id=task.id,
                old_status=old_status,
                new_status=new_status,
                changed_by=data.get("changed_by", "user"),
            )
            self._session.add(history)

        await self._session.flush()
        await log.ainfo("hub_task_updated", task_id=task_id, user_id=user_id)
        return task

    async def cancel_task(
        self,
        user_id: str,
        task_id: str,
        changed_by: str = "user",
    ) -> bool:
        """Soft-delete a task by setting its status to 'cancelled'.

        Never physically deletes — preserves the audit trail.
        Returns True if the task was found and cancelled, False otherwise.
        """
        task = await self.get_task(user_id, task_id)
        if task is None:
            return False

        old_status = task.status
        task.status = "cancelled"
        task.updated_at = datetime.now(timezone.utc)

        history = TaskStatusHistoryModel(
            task_id=task.id,
            old_status=old_status,
            new_status="cancelled",
            changed_by=changed_by,
        )
        self._session.add(history)
        await self._session.flush()

        await log.ainfo("hub_task_cancelled", task_id=task_id, user_id=user_id)
        return True

    async def add_dependency(self, task_id: str, depends_on_id: str) -> bool:
        """Create a dependency edge: task_id depends on depends_on_id.

        Returns True on success, False if the edge already exists.
        """
        stmt = select(TaskDependencyModel).where(
            TaskDependencyModel.task_id == uuid.UUID(task_id),
            TaskDependencyModel.depends_on_id == uuid.UUID(depends_on_id),
        )
        result = await self._session.execute(stmt)
        if result.scalar_one_or_none() is not None:
            return False

        dep = TaskDependencyModel(
            task_id=uuid.UUID(task_id),
            depends_on_id=uuid.UUID(depends_on_id),
        )
        self._session.add(dep)
        await self._session.flush()
        return True
