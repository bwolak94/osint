"""Data lineage and investigation versioning models."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.adapters.db.models import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DataLineageModel(Base):
    __tablename__ = "data_lineage"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    investigation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)  # scan_result, identity, node
    entity_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_scanner: Mapped[str] = mapped_column(String(100), nullable=False)
    source_input: Mapped[str] = mapped_column(String(1000), nullable=False)
    derived_from: Mapped[str | None] = mapped_column(String(255), nullable=True)  # parent entity ID
    transformation: Mapped[str] = mapped_column(String(100), default="direct", nullable=False)
    confidence: Mapped[float] = mapped_column(default=1.0, nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class InvestigationVersionModel(Base):
    __tablename__ = "investigation_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    investigation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    change_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
