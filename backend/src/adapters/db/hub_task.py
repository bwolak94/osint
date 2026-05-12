"""SQLAlchemy 2.0 async models for the Hub productivity task management system.

Tables:
  tasks                — user productivity tasks with priority and status tracking
  task_dependencies    — DAG of task prerequisite relationships
  task_status_history  — immutable audit log of status transitions
  productivity_events  — energy / outcome telemetry for cognitive load ML (Phase 3)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class HubBase(DeclarativeBase):
    """Declarative base scoped to the Hub task management models."""

    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TaskModel(HubBase):
    """A single productivity task belonging to a user."""

    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(SmallInteger, default=3, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        default="todo",
        nullable=False,
    )
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str] = mapped_column(String(64), default="user", nullable=False)
    source_ref_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('todo','in_progress','done','deferred','cancelled')",
            name="ck_tasks_status",
        ),
        CheckConstraint("priority BETWEEN 1 AND 5", name="ck_tasks_priority"),
        Index("ix_tasks_user_status", "user_id", "status"),
    )

    history: Mapped[list[TaskStatusHistoryModel]] = relationship(
        back_populates="task", cascade="all, delete-orphan", lazy="select"
    )


class TaskDependencyModel(HubBase):
    """Directed dependency edge: task_id depends on depends_on_id."""

    __tablename__ = "task_dependencies"

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    depends_on_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        primary_key=True,
    )


class TaskStatusHistoryModel(HubBase):
    """Immutable audit record of a task status transition."""

    __tablename__ = "task_status_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    old_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    new_status: Mapped[str] = mapped_column(String(32), nullable=False)
    changed_by: Mapped[str] = mapped_column(String(128), nullable=False, default="user")
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    task: Mapped[TaskModel] = relationship(back_populates="history")


class ProductivityEventModel(HubBase):
    """User productivity telemetry — used by the Phase 3 cognitive load ML model."""

    __tablename__ = "productivity_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    energy_self_report: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "outcome IN ('completed','deferred','abandoned')",
            name="ck_productivity_events_outcome",
        ),
        CheckConstraint(
            "energy_self_report IS NULL OR energy_self_report BETWEEN 1 AND 5",
            name="ck_productivity_events_energy",
        ),
    )
