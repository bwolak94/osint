"""SQLAlchemy ORM model for IMINT/GEOINT scans (Domain IV, Modules 61-80)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.adapters.db.models import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ImintModel(Base):
    __tablename__ = "imint_scans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    # Target: image URL, "lat,lon" coordinates, or plain URL
    target: Mapped[str] = mapped_column(String(2048), nullable=False)
    # "image_url" | "coordinates" | "url"
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # JSON array of module names executed
    modules_run: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # JSON object: {module_name: {found, data, error?, status}}
    results: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )

    def __repr__(self) -> str:
        return f"<ImintModel id={self.id} target={self.target!r} type={self.target_type!r}>"
