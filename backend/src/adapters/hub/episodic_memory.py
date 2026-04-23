"""EpisodicMemory — PostgreSQL-backed store for dismissed synergy signals.

Prevents the SynergyAgent from surfacing the same suggestion pattern within
a configurable cooldown window (default: 7 days).

Table: hub_episodic_memory
  id            UUID PK
  user_id       TEXT NOT NULL
  event_type    TEXT NOT NULL
  signal_id     TEXT NOT NULL
  context_hash  TEXT NOT NULL   -- hash of the signal payload for dedup
  reason        TEXT
  created_at    TIMESTAMPTZ DEFAULT now()

Design: DB session injected (DIP) — no direct SQLAlchemy import at module level.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

import structlog

log = structlog.get_logger(__name__)

_DEFAULT_COOLDOWN_DAYS = 7


class AsyncSession(Protocol):
    """Minimal async DB session protocol (subset of SQLAlchemy AsyncSession)."""

    async def execute(self, stmt: Any, params: Any = None) -> Any: ...
    async def commit(self) -> None: ...


def _hash_payload(payload: dict[str, Any]) -> str:
    """Stable SHA-256 hash of a signal payload for duplicate detection."""
    serialised = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(serialised.encode()).hexdigest()[:16]


class EpisodicMemory:
    """Records and queries dismissed synergy signals for a user.

    Args:
        db: Injected async SQLAlchemy session.
        cooldown_days: How long (in days) to suppress re-surfacing the same signal.
    """

    def __init__(
        self,
        db: AsyncSession,
        cooldown_days: int = _DEFAULT_COOLDOWN_DAYS,
    ) -> None:
        self._db = db
        self._cooldown_days = cooldown_days

    async def is_suppressed(
        self,
        user_id: str,
        payload: dict[str, Any],
    ) -> bool:
        """Return True if this signal pattern was dismissed within the cooldown window."""
        from sqlalchemy import text  # local import — avoids hard dep at module level

        context_hash = _hash_payload(payload)
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=self._cooldown_days)

        result = await self._db.execute(
            text(
                "SELECT 1 FROM hub_episodic_memory "
                "WHERE user_id = :user_id "
                "  AND context_hash = :context_hash "
                "  AND created_at > :cutoff "
                "LIMIT 1"
            ),
            {"user_id": user_id, "context_hash": context_hash, "cutoff": cutoff},
        )
        row = result.fetchone()
        return row is not None

    async def record_dismissal(
        self,
        user_id: str,
        signal_id: str,
        event_type: str,
        payload: dict[str, Any],
        reason: str = "user_dismissed",
    ) -> None:
        """Persist a dismissed signal to prevent repetition within the cooldown window."""
        from sqlalchemy import text

        context_hash = _hash_payload(payload)

        await self._db.execute(
            text(
                "INSERT INTO hub_episodic_memory "
                "(user_id, event_type, signal_id, context_hash, reason) "
                "VALUES (:user_id, :event_type, :signal_id, :context_hash, :reason)"
            ),
            {
                "user_id": user_id,
                "event_type": event_type,
                "signal_id": signal_id,
                "context_hash": context_hash,
                "reason": reason,
            },
        )
        await self._db.commit()

        await log.ainfo(
            "episodic_memory_recorded",
            user_id=user_id,
            signal_id=signal_id,
            event_type=event_type,
        )
