"""Queue depth monitor — inspect Celery queue backlogs via Redis.

GET /api/v1/workers/queue-depth
"""

from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User

log = structlog.get_logger(__name__)

router = APIRouter(tags=["queue-monitor"])

_QUEUES = ["heavy", "light", "graph", "pentest_heavy", "pentest_light", "celery"]
_CONGESTION_THRESHOLD = 50
_CRITICAL_THRESHOLD = 100


class QueueDepth(BaseModel):
    queue_name: str
    pending_tasks: int
    is_congested: bool


class QueueMonitorResponse(BaseModel):
    queues: list[QueueDepth]
    total_pending: int
    congested_queues: list[str]
    worker_status: str  # "healthy" / "congested"


@router.get("/workers/queue-depth", response_model=QueueMonitorResponse)
async def get_queue_depth(
    _: Annotated[User, Depends(get_current_user)],
) -> QueueMonitorResponse:
    """Return Celery queue depths by inspecting Redis list lengths."""
    queues: list[QueueDepth] = []

    try:
        from src.config import get_settings
        import redis.asyncio as aioredis

        settings = get_settings()
        redis_client = aioredis.from_url(str(settings.redis_url), decode_responses=True)

        for queue_name in _QUEUES:
            try:
                depth = await redis_client.llen(queue_name)
            except Exception:
                depth = 0
            queues.append(QueueDepth(
                queue_name=queue_name,
                pending_tasks=depth,
                is_congested=depth > _CONGESTION_THRESHOLD,
            ))

        await redis_client.aclose()
    except Exception as exc:
        log.debug("queue_monitor_redis_error", error=str(exc))
        queues = [
            QueueDepth(queue_name=q, pending_tasks=0, is_congested=False)
            for q in _QUEUES
        ]

    total_pending = sum(q.pending_tasks for q in queues)
    congested_queues = [q.queue_name for q in queues if q.is_congested]
    worker_status = "healthy" if total_pending < _CRITICAL_THRESHOLD else "congested"

    return QueueMonitorResponse(
        queues=queues,
        total_pending=total_pending,
        congested_queues=congested_queues,
        worker_status=worker_status,
    )
