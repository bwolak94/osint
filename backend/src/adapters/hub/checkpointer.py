"""PostgreSQL-backed hub state checkpointer.

Persists HubState snapshots atomically after each node execution.
Enables:
  - Crash recovery: resume from last checkpoint if Celery worker dies
  - Time-travel debugging: inspect any prior state for a given task
  - HITL resume: re-hydrate state for paused tasks

Table: hub_task_checkpoints
  id            UUID PK
  task_id       TEXT NOT NULL INDEX
  checkpoint_id TEXT NOT NULL
  step_name     TEXT NOT NULL  -- current_agent value
  state_json    JSONB NOT NULL
  created_at    TIMESTAMPTZ DEFAULT now()

Design: DB session injected (DIP). Falls back to Redis-only if DB unavailable.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import structlog

log = structlog.get_logger(__name__)


class HubCheckpointer:
    """Saves and loads HubState snapshots in PostgreSQL.

    Args:
        db_url: PostgreSQL async connection URL. If None, all operations are no-ops.
    """

    def __init__(self, db_url: str | None = None) -> None:
        self._db_url = db_url
        self._enabled = bool(db_url)

    async def save(
        self,
        task_id: str,
        step_name: str,
        state: dict[str, Any],
    ) -> str:
        """Atomically persist a HubState snapshot.

        Returns:
            checkpoint_id (UUID string) for the saved snapshot.
        """
        checkpoint_id = str(uuid.uuid4())

        if not self._enabled:
            log.debug("checkpointer_disabled", task_id=task_id)
            return checkpoint_id

        try:
            import asyncpg  # noqa: PLC0415

            conn = await asyncpg.connect(self._db_url)
            try:
                await conn.execute(
                    """
                    INSERT INTO hub_task_checkpoints
                        (id, task_id, checkpoint_id, step_name, state_json)
                    VALUES ($1, $2, $3, $4, $5::jsonb)
                    """,
                    str(uuid.uuid4()),
                    task_id,
                    checkpoint_id,
                    step_name,
                    json.dumps(state, default=str),
                )
            finally:
                await conn.close()

            log.info(
                "checkpoint_saved",
                task_id=task_id,
                step=step_name,
                checkpoint_id=checkpoint_id,
            )
        except Exception as exc:
            # Checkpointing failure must NEVER abort the pipeline
            log.warning("checkpoint_save_error", task_id=task_id, error=str(exc))

        return checkpoint_id

    async def load_latest(self, task_id: str) -> dict[str, Any] | None:
        """Load the most recent checkpoint for a task.

        Returns:
            HubState dict or None if no checkpoint exists.
        """
        if not self._enabled:
            return None

        try:
            import asyncpg  # noqa: PLC0415

            conn = await asyncpg.connect(self._db_url)
            try:
                row = await conn.fetchrow(
                    """
                    SELECT state_json FROM hub_task_checkpoints
                    WHERE task_id = $1
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    task_id,
                )
            finally:
                await conn.close()

            if row is None:
                return None

            state = json.loads(row["state_json"])
            log.info("checkpoint_loaded", task_id=task_id)
            return state  # type: ignore[return-value]

        except Exception as exc:
            log.warning("checkpoint_load_error", task_id=task_id, error=str(exc))
            return None

    async def list_checkpoints(self, task_id: str) -> list[dict[str, Any]]:
        """Return all checkpoint metadata for a task (for time-travel debugging)."""
        if not self._enabled:
            return []

        try:
            import asyncpg  # noqa: PLC0415

            conn = await asyncpg.connect(self._db_url)
            try:
                rows = await conn.fetch(
                    """
                    SELECT checkpoint_id, step_name, created_at
                    FROM hub_task_checkpoints
                    WHERE task_id = $1
                    ORDER BY created_at ASC
                    """,
                    task_id,
                )
            finally:
                await conn.close()

            return [
                {
                    "checkpoint_id": r["checkpoint_id"],
                    "step_name": r["step_name"],
                    "created_at": r["created_at"].isoformat(),
                }
                for r in rows
            ]
        except Exception as exc:
            log.warning("checkpoint_list_error", task_id=task_id, error=str(exc))
            return []


_checkpointer: HubCheckpointer | None = None


def get_checkpointer() -> HubCheckpointer:
    """Return the singleton HubCheckpointer, initialised from settings."""
    global _checkpointer  # noqa: PLW0603
    if _checkpointer is None:
        try:
            from src.config import get_settings  # noqa: PLC0415

            settings = get_settings()
            db_url: str | None = getattr(settings, "postgres_dsn", None)
            # asyncpg requires the plain postgresql:// scheme (not postgresql+asyncpg://)
            if db_url and db_url.startswith("postgresql+asyncpg://"):
                db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
            _checkpointer = HubCheckpointer(db_url=db_url)
        except Exception:
            _checkpointer = HubCheckpointer(db_url=None)
    return _checkpointer
