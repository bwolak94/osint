"""Basic Prometheus-compatible metrics endpoint."""

import time

from fastapi import APIRouter, Request
from starlette.responses import PlainTextResponse

router = APIRouter()

# Simple counters stored in module state
_start_time = time.time()


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics(request: Request) -> str:
    """Return basic metrics in Prometheus exposition format."""
    uptime = time.time() - _start_time

    lines = [
        "# HELP osint_up Whether the OSINT API is up",
        "# TYPE osint_up gauge",
        "osint_up 1",
        "",
        "# HELP osint_uptime_seconds Seconds since API started",
        "# TYPE osint_uptime_seconds gauge",
        f"osint_uptime_seconds {uptime:.2f}",
        "",
    ]

    # DB connection check
    try:
        from sqlalchemy import text

        from src.adapters.db.database import async_session_factory

        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        lines.append("osint_db_up 1")
    except Exception:
        lines.append("osint_db_up 0")

    # Redis check
    redis = getattr(request.app.state, "redis", None)
    if redis:
        try:
            await redis.ping()
            lines.append("osint_redis_up 1")
        except Exception:
            lines.append("osint_redis_up 0")
    else:
        lines.append("osint_redis_up 0")

    # Scanner duration histogram
    try:
        from src.adapters.scanners.metrics import prometheus_histogram_text
        lines.append("")
        lines.append(prometheus_histogram_text())
    except Exception:
        pass

    return "\n".join(lines) + "\n"
