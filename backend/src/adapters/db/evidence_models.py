"""Evidence tagging and saved search models."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.adapters.db.models import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EvidenceTagModel(Base):
    __tablename__ = "evidence_tags"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    investigation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    scan_result_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    node_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tag_name: Mapped[str] = mapped_column(String(100), nullable=False)
    tag_color: Mapped[str] = mapped_column(String(7), default="#6366f1", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class SavedSearchModel(Base):
    __tablename__ = "saved_searches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    filters: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    alert_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    alert_frequency: Mapped[str] = mapped_column(String(50), default="daily", nullable=False)
    last_alert_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
