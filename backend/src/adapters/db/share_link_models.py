"""Share link models for investigation sharing via tokens."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.adapters.db.models import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ShareLinkModel(Base):
    __tablename__ = "share_links"

    __table_args__ = (
        UniqueConstraint("token", name="uq_share_links_token"),
        Index("ix_share_links_token", "token", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_views: Mapped[int | None] = mapped_column(Integer, nullable=True)
    redact_pii: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allowed_node_types: Mapped[list | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<ShareLink id={self.id} token={self.token!r} is_active={self.is_active}>"
