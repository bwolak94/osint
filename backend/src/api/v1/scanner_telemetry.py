"""Scanner telemetry endpoint — performance metrics per scanner.

GET /api/v1/scanners/telemetry
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User

log = structlog.get_logger(__name__)

router = APIRouter(tags=["telemetry"])


class ScannerMetric(BaseModel):
    scanner_name: str
    scan_count: int
    avg_latency_ms: float
    error_count: int
    success_rate: float


class TelemetryResponse(BaseModel):
    total_scanners: int
    active_scanners: int
    metrics: list[ScannerMetric]
    collected_at: str


@router.get("/scanners/telemetry", response_model=TelemetryResponse)
async def get_scanner_telemetry(
    _: Annotated[User, Depends(get_current_user)],
) -> TelemetryResponse:
    """Collect and return scanner performance metrics from Redis."""
    from src.adapters.scanners.registry import get_default_registry

    try:
        registry = get_default_registry()
        all_scanners = list(registry._scanners.keys()) if hasattr(registry, "_scanners") else []
        total_scanners = len(all_scanners)
    except Exception:
        all_scanners = []
        total_scanners = 0

    metrics: list[ScannerMetric] = []

    try:
        from src.config import get_settings
        import redis.asyncio as aioredis

        settings = get_settings()
        redis_client = aioredis.from_url(str(settings.redis_url), decode_responses=True)

        for name in all_scanners:
            try:
                scan_count_raw = await redis_client.get(f"scanner:{name}:scan_count")
                avg_latency_raw = await redis_client.get(f"scanner:{name}:avg_latency_ms")
                error_count_raw = await redis_client.get(f"scanner:{name}:error_count")

                scan_count = int(scan_count_raw) if scan_count_raw else 0
                avg_latency = float(avg_latency_raw) if avg_latency_raw else 0.0
                error_count = int(error_count_raw) if error_count_raw else 0

                success_rate = (
                    round((scan_count - error_count) / scan_count, 4)
                    if scan_count > 0
                    else 1.0
                )
                success_rate = max(0.0, min(1.0, success_rate))

                metrics.append(ScannerMetric(
                    scanner_name=name,
                    scan_count=scan_count,
                    avg_latency_ms=avg_latency,
                    error_count=error_count,
                    success_rate=success_rate,
                ))
            except Exception:
                metrics.append(ScannerMetric(
                    scanner_name=name,
                    scan_count=0,
                    avg_latency_ms=0.0,
                    error_count=0,
                    success_rate=1.0,
                ))

        await redis_client.aclose()
    except Exception as exc:
        log.debug("scanner_telemetry_redis_error", error=str(exc))
        metrics = [
            ScannerMetric(
                scanner_name=name,
                scan_count=0,
                avg_latency_ms=0.0,
                error_count=0,
                success_rate=1.0,
            )
            for name in all_scanners
        ]

    active_scanners = sum(1 for m in metrics if m.scan_count > 0)

    return TelemetryResponse(
        total_scanners=total_scanners,
        active_scanners=active_scanners,
        metrics=metrics,
        collected_at=datetime.now(timezone.utc).isoformat(),
    )
