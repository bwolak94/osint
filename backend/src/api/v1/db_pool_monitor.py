"""Database connection pool monitor — expose SQLAlchemy pool stats.

GET /api/v1/db/pool-status
"""

from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User

log = structlog.get_logger(__name__)

router = APIRouter(tags=["db-monitoring"])


class DBPoolStatus(BaseModel):
    pool_size: int
    checked_out: int
    overflow: int
    available: int
    status: str
    health: str  # "healthy" / "degraded" / "critical"


@router.get("/db/pool-status", response_model=DBPoolStatus)
async def get_db_pool_status(
    _: Annotated[User, Depends(get_current_user)],
) -> DBPoolStatus:
    """Return SQLAlchemy async engine connection pool statistics."""
    from src.adapters.db.database import engine

    pool_size = 0
    checked_out = 0
    overflow = 0
    status_str = "unknown"

    try:
        pool = engine.pool
        pool_size = pool.size()
        checked_out = pool.checkedout()
        overflow = pool.overflow()
        status_str = pool.status()
    except Exception as exc:
        log.warning("db_pool_stats_failed", error=str(exc))
        status_str = f"error: {exc}"

    available = max(0, pool_size - checked_out)

    utilization = checked_out / pool_size if pool_size > 0 else 0.0
    if utilization < 0.7 and overflow <= 0:
        health = "healthy"
    elif utilization < 0.9 or overflow < 5:
        health = "degraded"
    else:
        health = "critical"

    return DBPoolStatus(
        pool_size=pool_size,
        checked_out=checked_out,
        overflow=overflow,
        available=available,
        status=status_str,
        health=health,
    )
