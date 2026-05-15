"""Periodic database cleanup tasks.

These tasks remove stale rows that accumulate over time and would otherwise
grow the database indefinitely without providing any value.
"""

import asyncio
from datetime import datetime, timezone

import structlog
from celery import shared_task
from sqlalchemy import delete

log = structlog.get_logger()


def _run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@shared_task(
    bind=True,
    name="src.workers.tasks.cleanup_tasks.purge_expired_refresh_tokens",
    queue="light",
)
def purge_expired_refresh_tokens(self) -> dict:
    """Delete refresh tokens whose expiry timestamp has passed.

    Refresh tokens are never deleted on normal use — only revoked. Without this
    task, the ``refresh_tokens`` table grows unboundedly. Run nightly via Beat.

    Returns:
        dict with key ``deleted`` indicating how many rows were removed.
    """

    async def _run() -> dict:
        from src.adapters.db.database import async_session_factory
        from src.adapters.db.models import RefreshTokenModel

        now = datetime.now(timezone.utc)
        async with async_session_factory() as session:
            result = await session.execute(
                delete(RefreshTokenModel).where(RefreshTokenModel.expires_at < now)
            )
            await session.commit()
            deleted = result.rowcount

        log.info("purge_expired_refresh_tokens.complete", deleted=deleted)
        return {"deleted": deleted}

    return _run_async(_run())
