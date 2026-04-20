"""SQLAlchemy ORM model for cloud storage exposure scans."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.adapters.db.models import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CloudExposureModel(Base):
    __tablename__ = "cloud_exposure_scans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    target: Mapped[str] = mapped_column(String(255), nullable=False)
    total_buckets: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    public_buckets: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sensitive_findings: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    buckets: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )

    def __repr__(self) -> str:
        return f"<CloudExposureModel id={self.id} target={self.target!r}>"
