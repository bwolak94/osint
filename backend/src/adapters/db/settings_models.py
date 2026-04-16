"""SQLAlchemy models for user and system settings."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.adapters.db.models import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserSettingsModel(Base):
    __tablename__ = "user_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )

    # UI
    theme: Mapped[str] = mapped_column(String(20), default="dark", nullable=False)
    language: Mapped[str] = mapped_column(String(5), default="pl", nullable=False)
    date_format: Mapped[str] = mapped_column(String(20), default="DD.MM.YYYY", nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="Europe/Warsaw", nullable=False)

    # Notifications
    email_on_scan_complete: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_on_new_findings: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_weekly_digest: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Investigation defaults
    default_scan_depth: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    default_enabled_scanners: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    default_tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)

    # Privacy
    anonymize_exports: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    data_retention_days: Mapped[int] = mapped_column(Integer, default=90, nullable=False)

    # API key
    api_key_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    api_key_prefix: Mapped[str | None] = mapped_column(String(16), nullable=True)
    api_key_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # GDPR
    gdpr_consent_given_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    marketing_consent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)


class SystemSettingsModel(Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    settings_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
