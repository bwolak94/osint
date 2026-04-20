"""TLP (Traffic Light Protocol) marking models for entity classification."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.adapters.db.models import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TLPMarkingModel(Base):
    __tablename__ = "tlp_markings"

    __table_args__ = (
        Index("ix_tlp_markings_entity", "entity_type", "entity_id"),
        Index("ix_tlp_markings_level", "tlp_level"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(255), nullable=False)
    tlp_level: Mapped[str] = mapped_column(String(10), nullable=False)
    marked_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    def __repr__(self) -> str:
        return (
            f"<TLPMarking id={self.id} entity_type={self.entity_type!r}"
            f" entity_id={self.entity_id!r} tlp_level={self.tlp_level!r}>"
        )
