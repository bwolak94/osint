"""SQLAlchemy ORM model for the hub_episodic_memory table (Phase 3).

Records dismissed synergy signals to prevent the SynergyAgent from
re-surfacing the same suggestion pattern within a cooldown window.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class HubEpisodicMemory(Base):
    """Dismissed synergy signal record.

    Each row stores a context_hash of the signal payload so that the
    EpisodicMemory adapter can quickly check for collisions within the
    cooldown window without persisting raw user data.
    """

    __tablename__ = "hub_episodic_memory"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    signal_id: Mapped[str] = mapped_column(String(36), nullable=False)
    context_hash: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(255), nullable=False, default="user_dismissed")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<HubEpisodicMemory user={self.user_id!r} "
            f"signal={self.signal_id!r} hash={self.context_hash!r}>"
        )
