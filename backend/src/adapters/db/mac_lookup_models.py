"""SQLAlchemy ORM model for MAC address lookups."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.adapters.db.models import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MacLookupModel(Base):
    __tablename__ = "mac_lookups"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    mac_address: Mapped[str] = mapped_column(String(17), nullable=False)
    oui_prefix: Mapped[str | None] = mapped_column(String(8), nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    manufacturer_country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    device_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_private: Mapped[bool | None] = mapped_column(nullable=True)
    is_multicast: Mapped[bool | None] = mapped_column(nullable=True)
    raw_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )

    def __repr__(self) -> str:
        return f"<MacLookupModel id={self.id} mac={self.mac_address!r}>"
