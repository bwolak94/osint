"""SQLAlchemy ORM model for fediverse scan results."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column
from src.adapters.db.models import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FediverseModel(Base):
    __tablename__ = "fediverse_scans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    query: Mapped[str] = mapped_column(String(255), nullable=False)
    total_results: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    platforms_searched: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    results: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )

    def __repr__(self) -> str:
        return f"<FediverseModel id={self.id} query={self.query!r}>"
