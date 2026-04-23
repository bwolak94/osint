"""SQLAlchemy 2.0 models for Hub Task Management (Phase 2 — 02.3)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.adapters.db.database import Base


class HubTask(Base):
    __tablename__ = "hub_tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="todo",
        server_default="todo",
    )
    due_at: Mapped[datetime | None] = mapped_column(nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="user")
    source_ref_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("priority BETWEEN 1 AND 5", name="hub_task_priority_range"),
        CheckConstraint(
            "status IN ('todo','in_progress','done','deferred','cancelled')",
            name="hub_task_status_valid",
        ),
    )

    dependencies: Mapped[list[HubTaskDependency]] = relationship(
        "HubTaskDependency",
        foreign_keys="HubTaskDependency.task_id",
        back_populates="task",
        cascade="all, delete-orphan",
    )
    history: Mapped[list[HubTaskStatusHistory]] = relationship(
        "HubTaskStatusHistory", back_populates="task", cascade="all, delete-orphan"
    )


class HubTaskDependency(Base):
    __tablename__ = "hub_task_dependencies"

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hub_tasks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    depends_on_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hub_tasks.id", ondelete="CASCADE"),
        primary_key=True,
    )

    task: Mapped[HubTask] = relationship(
        "HubTask", foreign_keys=[task_id], back_populates="dependencies"
    )


class HubTaskStatusHistory(Base):
    __tablename__ = "hub_task_status_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hub_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    old_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    new_status: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_by: Mapped[str] = mapped_column(String(100), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    task: Mapped[HubTask] = relationship("HubTask", back_populates="history")


class ProductivityEvent(Base):
    __tablename__ = "productivity_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(nullable=False)
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hub_tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    outcome: Mapped[str | None] = mapped_column(String(20), nullable=True)
    energy_self_report: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "outcome IN ('completed','deferred','abandoned')",
            name="productivity_event_outcome_valid",
        ),
        CheckConstraint(
            "energy_self_report BETWEEN 1 AND 5",
            name="productivity_event_energy_range",
        ),
    )
