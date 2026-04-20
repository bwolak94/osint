"""Playbook conditional branching models."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.adapters.db.models import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PlaybookConditionModel(Base):
    """A conditional branch within a playbook step."""
    __tablename__ = "playbook_conditions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    playbook_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    condition_type: Mapped[str] = mapped_column(String(50), nullable=False)  # result_contains, result_count_gt, scanner_status
    field_path: Mapped[str] = mapped_column(String(500), nullable=False)  # e.g., "raw_data.ports", "extracted_identifiers"
    operator: Mapped[str] = mapped_column(String(20), nullable=False)  # eq, ne, gt, lt, contains, exists
    expected_value: Mapped[str] = mapped_column(Text, default="", nullable=False)
    then_goto_step: Mapped[int | None] = mapped_column(Integer, nullable=True)  # jump to this step if true
    else_goto_step: Mapped[int | None] = mapped_column(Integer, nullable=True)  # jump if false
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<PlaybookCondition id={self.id} type={self.condition_type}>"


class InvestigationForkModel(Base):
    """Track investigation forks (branching from existing investigations)."""
    __tablename__ = "investigation_forks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_investigation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    child_investigation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True)
    fork_reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    forked_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    fork_point_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)  # snapshot of state at fork
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<InvestigationFork id={self.id} parent={self.parent_investigation_id}>"
