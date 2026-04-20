"""Activity feed endpoints — audit log and real-time activity stream."""

import asyncio
import json
import secrets
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

import structlog
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.api.v1.auth.dependencies import get_current_user

log = structlog.get_logger()
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ActivityEntryCreate(BaseModel):
    action: str = Field(..., min_length=1, max_length=100)
    entity_type: str | None = None
    entity_id: str | None = None
    metadata: dict[str, Any] = {}


class ActivityEntryResponse(BaseModel):
    id: str
    investigation_id: str
    actor_id: str
    action: str
    entity_type: str | None
    entity_id: str | None
    metadata: dict[str, Any]
    created_at: str


class ActivityFeedResponse(BaseModel):
    entries: list[ActivityEntryResponse]
    total: int
    skip: int
    limit: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry(investigation_id: str, actor_id: str, body: ActivityEntryCreate) -> ActivityEntryResponse:
    now = datetime.now(timezone.utc).isoformat()
    return ActivityEntryResponse(
        id=secrets.token_hex(16),
        investigation_id=investigation_id,
        actor_id=actor_id,
        action=body.action,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        metadata=body.metadata,
        created_at=now,
    )


async def _sse_event_generator(investigation_id: str) -> AsyncGenerator[str, None]:
    """
    Poll-based SSE generator.

    In production, subscribe to Redis channel
    `osint:inv:{investigation_id}:events` and yield events as they arrive.
    A heartbeat ping is sent every 15 seconds to keep the connection alive.
    The stream stops after a `pipeline_complete` event or 10 minutes (600s).
    """
    max_duration_seconds = 600
    heartbeat_interval = 15
    poll_interval = 1

    elapsed = 0.0
    since_heartbeat = 0.0

    while elapsed < max_duration_seconds:
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
        since_heartbeat += poll_interval

        # Heartbeat to keep the connection alive.
        if since_heartbeat >= heartbeat_interval:
            yield "data: ping\n\n"
            since_heartbeat = 0.0

        # Stub: real implementation would read from Redis and yield real events.
        # Example format:
        #   event: entity_discovered
        #   data: {"type": "domain", "value": "example.com", "depth": 1}

    # Signal end of stream.
    payload = json.dumps({"investigation_id": investigation_id, "reason": "timeout"})
    yield f"event: stream_closed\ndata: {payload}\n\n"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/investigations/{investigation_id}/activity", response_model=ActivityFeedResponse)
async def list_investigation_activity(
    investigation_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    action_filter: str | None = Query(None),
    current_user: Any = Depends(get_current_user),
) -> ActivityFeedResponse:
    """Return paginated activity log for a single investigation."""
    return ActivityFeedResponse(entries=[], total=0, skip=skip, limit=limit)


@router.get("/activity", response_model=ActivityFeedResponse)
async def list_global_activity(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: Any = Depends(get_current_user),
) -> ActivityFeedResponse:
    """Return global activity feed across all investigations owned by the current user."""
    return ActivityFeedResponse(entries=[], total=0, skip=skip, limit=limit)


@router.post(
    "/investigations/{investigation_id}/activity",
    response_model=ActivityEntryResponse,
    status_code=201,
)
async def log_activity_entry(
    investigation_id: str,
    body: ActivityEntryCreate,
    current_user: Any = Depends(get_current_user),
) -> ActivityEntryResponse:
    """
    Internal endpoint — log an activity entry.

    Intended for service-to-service calls or admin use.
    In production, restrict this to admin role or internal service tokens.
    """
    actor_id = str(getattr(current_user, "id", "unknown"))
    log.info("Activity entry logged", investigation_id=investigation_id, action=body.action, actor=actor_id)
    return _make_entry(investigation_id, actor_id, body)


@router.get("/investigations/{investigation_id}/activity/stream")
async def stream_investigation_activity(
    investigation_id: str,
    current_user: Any = Depends(get_current_user),
) -> StreamingResponse:
    """
    SSE endpoint streaming real-time activity events for an investigation.

    Events: scan_started, scan_completed, entity_discovered, pipeline_complete.
    Sends a heartbeat ping every 15 seconds.
    Connection closes after pipeline_complete or 10-minute timeout.
    """
    log.info("SSE activity stream started", investigation_id=investigation_id)
    return StreamingResponse(
        _sse_event_generator(investigation_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
