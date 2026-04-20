"""SQLAlchemy ORM model for document metadata checks."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Boolean
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.adapters.db.models import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DocMetadataModel(Base):
    __tablename__ = "doc_metadata_checks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    doc_format: Mapped[str | None] = mapped_column(String(20), nullable=True)  # pdf/docx/xlsx/pptx
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    creator_tool: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_modified_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at_doc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    modified_at_doc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revision_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    has_macros: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_hidden_content: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_tracked_changes: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    gps_lat: Mapped[float | None] = mapped_column(nullable=True)
    gps_lon: Mapped[float | None] = mapped_column(nullable=True)
    raw_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    embedded_files: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )

    def __repr__(self) -> str:
        return f"<DocMetadataModel id={self.id} filename={self.filename!r}>"
