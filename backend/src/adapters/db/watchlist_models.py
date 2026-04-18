"""Watch list models for continuous monitoring."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.adapters.db.models import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class WatchListItemModel(Base):
    __tablename__ = "watchlist_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    input_value: Mapped[str] = mapped_column(String(1000), nullable=False)
    input_type: Mapped[str] = mapped_column(String(50), nullable=False)
    scanners: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    schedule_cron: Mapped[str] = mapped_column(String(100), default="0 */6 * * *", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_on_change: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notification_channels: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    last_scan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_result_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scan_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    change_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_change_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<WatchListItem id={self.id} name={self.name!r}>"


class WebhookTriggerModel(Base):
    __tablename__ = "webhook_triggers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    secret_token: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    input_type: Mapped[str] = mapped_column(String(50), nullable=False)
    scanners: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    auto_start: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    trigger_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<WebhookTrigger id={self.id} name={self.name!r}>"
