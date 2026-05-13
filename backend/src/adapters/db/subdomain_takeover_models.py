"""SQLAlchemy ORM model for Subdomain Takeover scan results."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.adapters.db.models import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SubdomainTakeoverModel(Base):
    __tablename__ = "subdomain_takeover_scans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    total_subdomains: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    vulnerable_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    result: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )

    def __repr__(self) -> str:
        return f"<SubdomainTakeoverModel id={self.id} domain={self.domain!r}>"
