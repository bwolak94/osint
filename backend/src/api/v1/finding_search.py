"""Full-text finding search across all investigations.

GET /api/v1/findings/search?q=<query>&severity=high&scanner=shodan
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, or_, cast, String
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.auth.dependencies import get_current_user
from src.adapters.db.database import get_db
from src.adapters.db.models import InvestigationModel, ScanResultModel, UserModel

log = structlog.get_logger(__name__)

router = APIRouter()


class FindingSearchResult(BaseModel):
    investigation_id: str
    investigation_title: str | None
    scanner_name: str
    finding_type: str
    severity: str
    description: str
    source: str | None
    matched_fields: list[str]


class FindingSearchResponse(BaseModel):
    query: str
    total_matches: int
    results: list[FindingSearchResult]
    page: int
    page_size: int


@router.get("/findings/search", response_model=FindingSearchResponse, tags=["finding-search"])
async def search_findings(
    q: str = Query(..., min_length=2, description="Search query"),
    severity: str | None = Query(None, description="Filter by severity: critical|high|medium|low|info"),
    scanner: str | None = Query(None, description="Filter by scanner name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> FindingSearchResponse:
    """Search across all findings in all user investigations."""
    q_lower = q.lower()

    # Get user's investigation IDs first
    inv_result = await db.execute(
        select(InvestigationModel.id, InvestigationModel.title).where(
            InvestigationModel.owner_id == current_user.id
        )
    )
    inv_rows = inv_result.all()
    inv_map = {str(row.id): row.title for row in inv_rows}
    inv_ids = list(inv_map.keys())

    if not inv_ids:
        return FindingSearchResponse(
            query=q, total_matches=0, results=[], page=page, page_size=page_size
        )

    # Fetch scan results — filter by scanner if specified
    query_obj = select(ScanResultModel).where(
        ScanResultModel.investigation_id.in_(inv_ids)
    )
    if scanner:
        query_obj = query_obj.where(ScanResultModel.scanner_name == scanner)

    query_obj = query_obj.limit(500)
    sr_result = await db.execute(query_obj)
    scan_results = sr_result.scalars().all()

    matches: list[FindingSearchResult] = []
    for sr in scan_results:
        findings = (sr.raw_data or {}).get("findings", [])
        for f in findings:
            ftype = f.get("type", "")
            sev = f.get("severity", "info").lower()
            desc = f.get("description", "")
            source = f.get("source", "")

            # Apply severity filter
            if severity and sev != severity.lower():
                continue

            # Text search across key fields
            search_text = " ".join(str(v) for v in f.values() if isinstance(v, (str, int, float))).lower()
            if q_lower not in search_text:
                continue

            # Identify which fields matched
            matched_fields = [
                k for k, v in f.items()
                if isinstance(v, str) and q_lower in v.lower()
            ]

            matches.append(FindingSearchResult(
                investigation_id=str(sr.investigation_id),
                investigation_title=inv_map.get(str(sr.investigation_id)),
                scanner_name=sr.scanner_name or "",
                finding_type=ftype,
                severity=sev,
                description=desc[:300],
                source=source,
                matched_fields=matched_fields[:5],
            ))

    total = len(matches)
    offset = (page - 1) * page_size
    paginated = matches[offset:offset + page_size]

    return FindingSearchResponse(
        query=q,
        total_matches=total,
        results=paginated,
        page=page,
        page_size=page_size,
    )
