"""Scan profile models for configuring scanner behaviour."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.adapters.db.models import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ScanProfileModel(Base):
    __tablename__ = "scan_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    enabled_scanners: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    disabled_scanners: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    proxy_mode: Mapped[str] = mapped_column(String(50), default="direct", nullable=False)
    timeout_override: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cache_bypass: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    max_concurrent: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<ScanProfile id={self.id} name={self.name!r} proxy_mode={self.proxy_mode!r}>"
