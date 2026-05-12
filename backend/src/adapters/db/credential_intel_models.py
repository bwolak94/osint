"""SQLAlchemy ORM model for Credential Intelligence scans (Domain III, Modules 41-60)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.adapters.db.models import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CredentialIntelModel(Base):
    __tablename__ = "credential_intel_scans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    target: Mapped[str] = mapped_column(String(255), nullable=False)
    # "email" | "domain" | "ip" | "hash"
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    modules_run: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    results: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )

    def __repr__(self) -> str:
        return f"<CredentialIntelModel id={self.id} target={self.target!r}>"
