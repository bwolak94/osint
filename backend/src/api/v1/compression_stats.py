"""Finding compression statistics — storage analysis for scan results.

GET /api/v1/storage/compression-stats
"""

from __future__ import annotations

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.auth.dependencies import get_current_user
from src.adapters.db.database import get_db
from src.core.domain.entities.user import User

log = structlog.get_logger(__name__)

router = APIRouter(tags=["storage"])

_COMPRESSION_RATIO = 3.0


class CompressionStatsResponse(BaseModel):
    total_scan_results: int
    avg_raw_data_bytes: float
    estimated_total_bytes: float
    estimated_compressed_bytes: float
    compression_ratio: float
    largest_scanners: list[dict[str, Any]]


@router.get("/storage/compression-stats", response_model=CompressionStatsResponse)
async def get_compression_stats(
    _: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> CompressionStatsResponse:
    """Return storage statistics and estimated compression savings for scan results."""
    total_count = 0
    avg_bytes = 0.0
    largest_scanners: list[dict[str, Any]] = []

    try:
        count_result = await db.execute(
            text("SELECT COUNT(*), COALESCE(AVG(pg_column_size(raw_data)), 0) FROM scan_results")
        )
        row = count_result.fetchone()
        if row:
            total_count = int(row[0]) if row[0] else 0
            avg_bytes = float(row[1]) if row[1] else 0.0
    except Exception as exc:
        log.warning("compression_stats_count_failed", error=str(exc))

    try:
        top_result = await db.execute(
            text(
                """
                SELECT scanner_name,
                       COALESCE(AVG(pg_column_size(raw_data)), 0) AS avg_bytes
                FROM scan_results
                GROUP BY scanner_name
                ORDER BY avg_bytes DESC
                LIMIT 5
                """
            )
        )
        for r in top_result.fetchall():
            largest_scanners.append({
                "scanner_name": r[0] or "unknown",
                "avg_bytes": round(float(r[1]), 2),
            })
    except Exception as exc:
        log.warning("compression_stats_top_failed", error=str(exc))

    estimated_total = avg_bytes * total_count
    estimated_compressed = estimated_total / _COMPRESSION_RATIO

    return CompressionStatsResponse(
        total_scan_results=total_count,
        avg_raw_data_bytes=round(avg_bytes, 2),
        estimated_total_bytes=round(estimated_total, 2),
        estimated_compressed_bytes=round(estimated_compressed, 2),
        compression_ratio=_COMPRESSION_RATIO,
        largest_scanners=largest_scanners,
    )
