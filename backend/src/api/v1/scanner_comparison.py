"""Scanner comparison — side-by-side comparison of scan results across multiple targets.

POST /api/v1/scanner/compare — compare scan results for multiple targets
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.auth.dependencies import get_current_user
from src.adapters.db.database import get_db
from src.adapters.db.models import ScanResultModel, UserModel

log = structlog.get_logger(__name__)

router = APIRouter()


class CompareRequest(BaseModel):
    investigation_ids: list[str]
    scanner_names: list[str] | None = None

    @field_validator("investigation_ids")
    @classmethod
    def validate_count(cls, v: list[str]) -> list[str]:
        if len(v) < 2:
            raise ValueError("At least 2 investigation IDs required for comparison")
        if len(v) > 5:
            raise ValueError("Maximum 5 investigations can be compared at once")
        return v


class ScannerComparisonRow(BaseModel):
    scanner_name: str
    results_per_investigation: dict[str, dict[str, Any]]


class ComparisonResponse(BaseModel):
    investigation_ids: list[str]
    comparison_rows: list[ScannerComparisonRow]
    shared_scanners: list[str]
    unique_findings_per_investigation: dict[str, int]
    severity_summary: dict[str, dict[str, int]]


@router.post("/scanner/compare", response_model=ComparisonResponse, tags=["scanner-compare"])
async def compare_scans(
    req: CompareRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> ComparisonResponse:
    """Compare scan results across multiple investigations side by side."""

    # Fetch scan results for all investigations
    inv_results: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for inv_id in req.investigation_ids:
        result = await db.execute(
            select(ScanResultModel).where(
                ScanResultModel.investigation_id == inv_id
            ).limit(100)
        )
        scan_results = result.scalars().all()
        inv_results[inv_id] = {}
        for sr in scan_results:
            scanner = sr.scanner_name or "unknown"
            if req.scanner_names and scanner not in req.scanner_names:
                continue
            inv_results[inv_id][scanner] = (sr.raw_data or {}).get("findings", [])

    # Find scanners that appear in all investigations
    all_scanner_sets = [set(scanners.keys()) for scanners in inv_results.values()]
    shared_scanners = sorted(set.intersection(*all_scanner_sets)) if all_scanner_sets else []

    # Build comparison rows
    all_scanners = sorted(set(
        scanner
        for inv_scanners in inv_results.values()
        for scanner in inv_scanners
    ))
    rows: list[ScannerComparisonRow] = []
    for scanner in all_scanners:
        per_inv: dict[str, dict[str, Any]] = {}
        for inv_id in req.investigation_ids:
            findings = inv_results[inv_id].get(scanner, [])
            per_inv[inv_id] = {
                "finding_count": len(findings),
                "has_data": len(findings) > 0,
                "severity_counts": _count_severities(findings),
                "top_finding": findings[0].get("description", "") if findings else None,
            }
        rows.append(ScannerComparisonRow(
            scanner_name=scanner,
            results_per_investigation=per_inv,
        ))

    # Unique findings count
    unique_counts = {
        inv_id: sum(len(f) for f in scanners.values())
        for inv_id, scanners in inv_results.items()
    }

    # Severity summary per investigation
    severity_summary: dict[str, dict[str, int]] = {}
    for inv_id, scanners in inv_results.items():
        all_findings = [f for findings in scanners.values() for f in findings]
        severity_summary[inv_id] = _count_severities(all_findings)

    return ComparisonResponse(
        investigation_ids=req.investigation_ids,
        comparison_rows=rows,
        shared_scanners=shared_scanners,
        unique_findings_per_investigation=unique_counts,
        severity_summary=severity_summary,
    )


def _count_severities(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for f in findings:
        sev = f.get("severity", "info").lower()
        counts[sev] = counts.get(sev, 0) + 1
    return counts
