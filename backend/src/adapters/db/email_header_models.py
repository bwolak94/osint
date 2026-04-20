"""SQLAlchemy ORM model for email header analysis."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Boolean
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.adapters.db.models import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EmailHeaderModel(Base):
    __tablename__ = "email_header_checks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sender_from: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sender_reply_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    originating_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    originating_country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    originating_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    spf_result: Mapped[str | None] = mapped_column(String(20), nullable=True)
    dkim_result: Mapped[str | None] = mapped_column(String(20), nullable=True)
    dmarc_result: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_spoofed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    hops: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    raw_headers_summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )

    def __repr__(self) -> str:
        return f"<EmailHeaderModel id={self.id} subject={self.subject!r}>"
