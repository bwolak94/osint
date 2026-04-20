"""SQLAlchemy ORM model for supply chain / package intelligence scans."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.adapters.db.models import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SupplyChainModel(Base):
    __tablename__ = "supply_chain_scans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    target: Mapped[str] = mapped_column(String(255), nullable=False)
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)  # domain/github_user/github_org
    total_packages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cves: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    packages: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )

    def __repr__(self) -> str:
        return f"<SupplyChainModel id={self.id} target={self.target!r}>"
