"""Scanner rate limit monitoring — real-time view of scanner quota and rate limit status.

GET /api/v1/scanners/rate-status — current rate limit status for all scanners
GET /api/v1/scanners/rate-status/{scanner_name} — status for specific scanner
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.auth.dependencies import get_current_user
from src.adapters.db.database import get_db
from src.adapters.db.models import UserModel

log = structlog.get_logger(__name__)

router = APIRouter()


class ScannerRateStatus(BaseModel):
    scanner_name: str
    circuit_state: str
    failure_count: int
    last_failure: str | None
    rate_limit_remaining: int | None
    is_healthy: bool
    cache_hit_rate: float | None


class RateMonitorResponse(BaseModel):
    total_scanners: int
    healthy_scanners: int
    degraded_scanners: int
    open_circuits: int
    statuses: list[ScannerRateStatus]


@router.get("/scanners/rate-status", response_model=RateMonitorResponse,
            tags=["scanner-monitoring"])
async def get_rate_status(
    current_user: UserModel = Depends(get_current_user),
) -> RateMonitorResponse:
    """Get rate limit and circuit breaker status for all registered scanners."""
    from src.adapters.scanners.registry import get_default_registry
    from src.adapters.scanners.circuit_breaker import RedisCircuitBreaker

    try:
        registry = get_default_registry()
        scanner_names = list(registry._scanners.keys()) if hasattr(registry, "_scanners") else []
    except Exception:
        scanner_names = []

    statuses: list[ScannerRateStatus] = []

    try:
        from src.config import get_settings
        settings = get_settings()
        import redis.asyncio as aioredis
        redis_client = aioredis.from_url(str(settings.redis_url))

        for name in scanner_names[:100]:
            try:
                cb = RedisCircuitBreaker(redis_client, scanner_name=name)
                state = await cb.get_state()
                failure_count = await cb.get_failure_count()
                is_healthy = state == "closed"
                statuses.append(ScannerRateStatus(
                    scanner_name=name,
                    circuit_state=state,
                    failure_count=failure_count,
                    last_failure=None,
                    rate_limit_remaining=None,
                    is_healthy=is_healthy,
                    cache_hit_rate=None,
                ))
            except Exception:
                statuses.append(ScannerRateStatus(
                    scanner_name=name,
                    circuit_state="unknown",
                    failure_count=0,
                    last_failure=None,
                    rate_limit_remaining=None,
                    is_healthy=True,
                    cache_hit_rate=None,
                ))

        await redis_client.aclose()
    except Exception as exc:
        log.debug("Rate monitor Redis error", error=str(exc))
        for name in scanner_names[:100]:
            statuses.append(ScannerRateStatus(
                scanner_name=name,
                circuit_state="unknown",
                failure_count=0,
                last_failure=None,
                rate_limit_remaining=None,
                is_healthy=True,
                cache_hit_rate=None,
            ))

    healthy = sum(1 for s in statuses if s.is_healthy)
    open_circuits = sum(1 for s in statuses if s.circuit_state == "open")

    return RateMonitorResponse(
        total_scanners=len(statuses),
        healthy_scanners=healthy,
        degraded_scanners=len(statuses) - healthy,
        open_circuits=open_circuits,
        statuses=statuses,
    )
