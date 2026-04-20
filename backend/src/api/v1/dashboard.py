"""Executive dashboard widget endpoints."""

from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from src.api.v1.auth.dependencies import get_current_user

log = structlog.get_logger()
router = APIRouter()


class DashboardStats(BaseModel):
    total_investigations: int
    active_investigations: int
    completed_investigations: int
    total_scans: int
    successful_scans: int
    failed_scans: int
    total_identities: int
    total_iocs: int
    avg_scan_duration_ms: int


class TrendDataPoint(BaseModel):
    date: str
    value: int


class DashboardTrends(BaseModel):
    investigations_over_time: list[TrendDataPoint]
    scans_over_time: list[TrendDataPoint]
    findings_over_time: list[TrendDataPoint]


class ScannerPerformance(BaseModel):
    scanner_name: str
    total_runs: int
    success_rate: float
    avg_duration_ms: int
    last_run: str | None


class TopFinding(BaseModel):
    type: str
    value: str
    count: int
    severity: str


class DashboardWidgetsResponse(BaseModel):
    stats: DashboardStats
    trends: DashboardTrends
    scanner_performance: list[ScannerPerformance]
    top_findings: list[TopFinding]
    recent_activity: list[dict[str, Any]]


@router.get("/dashboard/widgets", response_model=DashboardWidgetsResponse)
async def get_dashboard_widgets(
    period: str = Query("30d", pattern="^(7d|30d|90d|1y)$"),
    current_user: Any = Depends(get_current_user),
) -> DashboardWidgetsResponse:
    """Get all executive dashboard widget data."""
    return DashboardWidgetsResponse(
        stats=DashboardStats(
            total_investigations=0,
            active_investigations=0,
            completed_investigations=0,
            total_scans=0,
            successful_scans=0,
            failed_scans=0,
            total_identities=0,
            total_iocs=0,
            avg_scan_duration_ms=0,
        ),
        trends=DashboardTrends(
            investigations_over_time=[],
            scans_over_time=[],
            findings_over_time=[],
        ),
        scanner_performance=[],
        top_findings=[],
        recent_activity=[],
    )


@router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    current_user: Any = Depends(get_current_user),
) -> DashboardStats:
    """Get high-level statistics."""
    return DashboardStats(
        total_investigations=0, active_investigations=0, completed_investigations=0,
        total_scans=0, successful_scans=0, failed_scans=0,
        total_identities=0, total_iocs=0, avg_scan_duration_ms=0,
    )


@router.get("/dashboard/scanner-performance", response_model=list[ScannerPerformance])
async def get_scanner_performance(
    current_user: Any = Depends(get_current_user),
) -> list[ScannerPerformance]:
    """Get performance metrics for each scanner."""
    return []
