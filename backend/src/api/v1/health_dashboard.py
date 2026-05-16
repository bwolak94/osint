"""Comprehensive system health dashboard — aggregated status for all services.

GET /api/v1/health/dashboard  (no auth required)
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.database import get_db

log = structlog.get_logger(__name__)

router = APIRouter(tags=["health-dashboard"])


class ServiceHealth(BaseModel):
    name: str
    status: str  # healthy / degraded / down
    latency_ms: float | None
    detail: str | None


class HealthDashboardResponse(BaseModel):
    overall_status: str
    services: list[ServiceHealth]
    scanner_count: int
    checked_at: str


async def _check_postgres(db: AsyncSession) -> ServiceHealth:
    t0 = time.perf_counter()
    try:
        await db.execute(text("SELECT 1"))
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return ServiceHealth(name="postgresql", status="healthy", latency_ms=latency_ms, detail=None)
    except Exception as exc:
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return ServiceHealth(name="postgresql", status="down", latency_ms=latency_ms, detail=str(exc))


async def _check_redis() -> ServiceHealth:
    t0 = time.perf_counter()
    try:
        from src.config import get_settings
        import redis.asyncio as aioredis

        settings = get_settings()
        redis_client = aioredis.from_url(str(settings.redis_url), decode_responses=True)
        await redis_client.ping()
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        await redis_client.aclose()
        return ServiceHealth(name="redis", status="healthy", latency_ms=latency_ms, detail=None)
    except Exception as exc:
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return ServiceHealth(name="redis", status="down", latency_ms=latency_ms, detail=str(exc))


async def _check_neo4j() -> ServiceHealth:
    t0 = time.perf_counter()
    try:
        import aiohttp
        from src.config import get_settings

        settings = get_settings()
        neo4j_uri = getattr(settings, "neo4j_uri", "bolt://neo4j:7687")
        # Convert bolt:// to http:// for the browser endpoint
        http_uri = neo4j_uri.replace("bolt://", "http://").replace("neo4j://", "http://")
        # Strip credentials if present, use standard browser port
        host = http_uri.split("@")[-1].split(":")[0]
        health_url = f"http://{host}:7474"

        timeout = aiohttp.ClientTimeout(total=3.0)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(health_url) as resp:
                latency_ms = round((time.perf_counter() - t0) * 1000, 2)
                if resp.status < 500:
                    return ServiceHealth(name="neo4j", status="healthy", latency_ms=latency_ms, detail=None)
                return ServiceHealth(name="neo4j", status="degraded", latency_ms=latency_ms, detail=f"HTTP {resp.status}")
    except Exception as exc:
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return ServiceHealth(name="neo4j", status="down", latency_ms=latency_ms, detail=str(exc))


async def _check_scanner_registry() -> tuple[ServiceHealth, int]:
    t0 = time.perf_counter()
    scanner_count = 0
    try:
        from src.adapters.scanners.registry import get_default_registry

        registry = get_default_registry()
        scanner_count = len(registry._scanners) if hasattr(registry, "_scanners") else 0
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return (
            ServiceHealth(name="scanner_registry", status="healthy", latency_ms=latency_ms, detail=f"{scanner_count} scanners"),
            scanner_count,
        )
    except Exception as exc:
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return (
            ServiceHealth(name="scanner_registry", status="down", latency_ms=latency_ms, detail=str(exc)),
            0,
        )


@router.get("/health/dashboard", response_model=HealthDashboardResponse)
async def get_health_dashboard(
    db: AsyncSession = Depends(get_db),
) -> HealthDashboardResponse:
    """Comprehensive health check for all platform services. No auth required."""
    pg_task = _check_postgres(db)
    redis_task = _check_redis()
    neo4j_task = _check_neo4j()
    registry_task = _check_scanner_registry()

    pg_health, redis_health, neo4j_health, (registry_health, scanner_count) = await asyncio.gather(
        pg_task, redis_task, neo4j_task, registry_task
    )

    services = [pg_health, redis_health, neo4j_health, registry_health]

    statuses = {s.status for s in services}
    if "down" in statuses:
        overall = "degraded" if statuses != {"down"} else "down"
    elif "degraded" in statuses:
        overall = "degraded"
    else:
        overall = "healthy"

    return HealthDashboardResponse(
        overall_status=overall,
        services=services,
        scanner_count=scanner_count,
        checked_at=datetime.now(timezone.utc).isoformat(),
    )
