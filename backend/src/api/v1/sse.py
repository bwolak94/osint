"""Server-Sent Events endpoint for real-time scan progress streaming."""

import asyncio
import json
from typing import Any, AsyncGenerator

import structlog
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from src.api.v1.auth.dependencies import get_current_user

log = structlog.get_logger()
router = APIRouter()

# SSE timing constants
_HEARTBEAT_INTERVAL_SECONDS = 15
_POLL_INTERVAL_SECONDS = 1
_MAX_STREAM_DURATION_SECONDS = 600  # 10 minutes


# ---------------------------------------------------------------------------
# SSE generator
# ---------------------------------------------------------------------------


async def _scan_event_generator(investigation_id: str) -> AsyncGenerator[str, None]:
    """
    Yield SSE-formatted events for ongoing scan progress.

    Polls Redis channel `osint:inv:{investigation_id}:events` every second.
    Emits a heartbeat ping every 15 seconds to prevent proxy timeouts.
    Terminates after a `pipeline_complete` event or a 10-minute hard cap.

    Expected event types:
      - scan_started        {"scanner": str, "input": str}
      - scan_completed      {"scanner": str, "input": str, "findings": int}
      - entity_discovered   {"type": str, "value": str, "depth": int}
      - pipeline_complete   {"investigation_id": str, "total_findings": int}
    """
    elapsed = 0.0
    since_heartbeat = 0.0

    while elapsed < _MAX_STREAM_DURATION_SECONDS:
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)
        elapsed += _POLL_INTERVAL_SECONDS
        since_heartbeat += _POLL_INTERVAL_SECONDS

        if since_heartbeat >= _HEARTBEAT_INTERVAL_SECONDS:
            yield "data: ping\n\n"
            since_heartbeat = 0.0

        # Stub: real implementation would call something like:
        #
        #   raw = await redis.lpop(f"osint:inv:{investigation_id}:events")
        #   if raw:
        #       event = json.loads(raw)
        #       yield f"event: {event['type']}\ndata: {json.dumps(event['data'])}\n\n"
        #       if event['type'] == 'pipeline_complete':
        #           return

    # Hard timeout — signal client to stop reconnecting.
    payload = json.dumps({"investigation_id": investigation_id, "reason": "timeout"})
    yield f"event: stream_closed\ndata: {payload}\n\n"


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get("/investigations/{investigation_id}/stream")
async def stream_scan_events(
    investigation_id: str,
    current_user: Any = Depends(get_current_user),
) -> StreamingResponse:
    """
    SSE stream for scan progress events tied to a specific investigation.

    Streams events:
      - ``scan_started``       — a scanner has begun processing
      - ``scan_completed``     — a scanner finished with N findings
      - ``entity_discovered``  — a new graph entity was found
      - ``pipeline_complete``  — all scanners finished; stream will close

    Example response chunks::

        event: scan_completed
        data: {"scanner": "shodan", "input": "8.8.8.8", "findings": 3}

        event: entity_discovered
        data: {"type": "domain", "value": "example.com", "depth": 1}

    A ``data: ping`` heartbeat is sent every 15 seconds to keep the
    connection alive through proxies that close idle connections.
    The stream terminates after ``pipeline_complete`` or 10 minutes.
    """
    log.info("SSE scan stream opened", investigation_id=investigation_id)
    return StreamingResponse(
        _scan_event_generator(investigation_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
