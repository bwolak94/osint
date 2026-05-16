"""Registry pre-warm endpoint — force scanner registry initialization and report timing.

POST /api/v1/scanners/prewarm        — trigger pre-warm
GET  /api/v1/scanners/prewarm/status — check pre-warm status
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User

log = structlog.get_logger(__name__)

router = APIRouter(tags=["registry"])

_PREWARM_TS_KEY = "registry:prewarm_ts"


class PrewarmResponse(BaseModel):
    status: str  # "triggered" or "already_warm"
    scanner_count: int
    duration_ms: float
    last_prewarm: str | None


class PrewarmStatusResponse(BaseModel):
    last_prewarm: str | None
    seconds_since_prewarm: float | None
    scanner_count: int


@router.post("/scanners/prewarm", response_model=PrewarmResponse)
async def trigger_prewarm(
    _: Annotated[User, Depends(get_current_user)],
) -> PrewarmResponse:
    """Force scanner registry initialization and record timestamp in Redis."""
    from src.adapters.scanners.registry import get_default_registry

    t0 = time.perf_counter()
    scanner_count = 0
    try:
        registry = get_default_registry()
        scanner_count = len(registry._scanners) if hasattr(registry, "_scanners") else 0
    except Exception as exc:
        log.warning("prewarm_registry_failed", error=str(exc))

    duration_ms = round((time.perf_counter() - t0) * 1000, 2)
    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        from src.config import get_settings
        import redis.asyncio as aioredis

        settings = get_settings()
        redis_client = aioredis.from_url(str(settings.redis_url), decode_responses=True)
        await redis_client.set(_PREWARM_TS_KEY, now_iso)
        await redis_client.aclose()
    except Exception as exc:
        log.debug("prewarm_redis_write_failed", error=str(exc))

    return PrewarmResponse(
        status="triggered",
        scanner_count=scanner_count,
        duration_ms=duration_ms,
        last_prewarm=now_iso,
    )


@router.get("/scanners/prewarm/status", response_model=PrewarmStatusResponse)
async def get_prewarm_status(
    _: Annotated[User, Depends(get_current_user)],
) -> PrewarmStatusResponse:
    """Check when the registry was last pre-warmed."""
    from src.adapters.scanners.registry import get_default_registry

    scanner_count = 0
    try:
        registry = get_default_registry()
        scanner_count = len(registry._scanners) if hasattr(registry, "_scanners") else 0
    except Exception:
        pass

    last_prewarm: str | None = None
    seconds_since: float | None = None

    try:
        from src.config import get_settings
        import redis.asyncio as aioredis

        settings = get_settings()
        redis_client = aioredis.from_url(str(settings.redis_url), decode_responses=True)
        last_prewarm = await redis_client.get(_PREWARM_TS_KEY)
        await redis_client.aclose()

        if last_prewarm:
            ts = datetime.fromisoformat(last_prewarm)
            now = datetime.now(timezone.utc)
            seconds_since = round((now - ts).total_seconds(), 1)
    except Exception as exc:
        log.debug("prewarm_status_redis_error", error=str(exc))

    return PrewarmStatusResponse(
        last_prewarm=last_prewarm,
        seconds_since_prewarm=seconds_since,
        scanner_count=scanner_count,
    )
