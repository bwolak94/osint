"""API response cache statistics and flush operations.

GET    /api/v1/cache/stats
DELETE /api/v1/cache/flush-all — flush all scanner caches (auth required)
"""

from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User

log = structlog.get_logger(__name__)

router = APIRouter(tags=["cache-stats"])


class CacheStatsResponse(BaseModel):
    hit_rate: float
    total_hits: int
    total_misses: int
    scanner_cache_keys: int
    memory_used: str
    total_commands: int


class FlushAllResponse(BaseModel):
    keys_deleted: int
    status: str


@router.get("/cache/stats", response_model=CacheStatsResponse)
async def get_cache_stats(
    _: Annotated[User, Depends(get_current_user)],
) -> CacheStatsResponse:
    """Return Redis cache statistics including hit rate and memory usage."""
    try:
        from src.config import get_settings
        import redis.asyncio as aioredis

        settings = get_settings()
        redis_client = aioredis.from_url(str(settings.redis_url), decode_responses=True)

        info = await redis_client.info("stats")
        hits = int(info.get("keyspace_hits", 0))
        misses = int(info.get("keyspace_misses", 0))
        total_commands = int(info.get("total_commands_processed", 0))

        memory_info = await redis_client.info("memory")
        memory_used = str(memory_info.get("used_memory_human", "unknown"))

        scanner_keys = await redis_client.keys("scanner:*")
        scanner_cache_keys = len(scanner_keys)

        await redis_client.aclose()
    except Exception as exc:
        log.debug("cache_stats_redis_error", error=str(exc))
        raise HTTPException(status_code=503, detail="Redis unavailable") from exc

    total = hits + misses
    hit_rate = round(hits / total, 4) if total > 0 else 0.0

    return CacheStatsResponse(
        hit_rate=hit_rate,
        total_hits=hits,
        total_misses=misses,
        scanner_cache_keys=scanner_cache_keys,
        memory_used=memory_used,
        total_commands=total_commands,
    )


@router.delete("/cache/flush-all", response_model=FlushAllResponse)
async def flush_all_scanner_caches(
    _: Annotated[User, Depends(get_current_user)],
) -> FlushAllResponse:
    """Delete all scanner cache keys from Redis. Requires authentication."""
    try:
        from src.config import get_settings
        import redis.asyncio as aioredis

        settings = get_settings()
        redis_client = aioredis.from_url(str(settings.redis_url), decode_responses=True)

        keys = await redis_client.keys("scanner:*")
        deleted = 0
        if keys:
            deleted = await redis_client.delete(*keys)

        await redis_client.aclose()
    except Exception as exc:
        log.warning("cache_flush_all_failed", error=str(exc))
        raise HTTPException(status_code=503, detail="Redis unavailable") from exc

    return FlushAllResponse(keys_deleted=deleted, status="flushed")
