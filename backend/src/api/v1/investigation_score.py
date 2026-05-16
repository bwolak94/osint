"""Investigation completeness score — measure how thoroughly an investigation has been done.

GET /api/v1/investigations/{id}/completeness — return completeness score with coverage gaps
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.auth.dependencies import get_current_user
from src.adapters.db.database import get_db
from src.adapters.db.models import ScanResultModel, UserModel

log = structlog.get_logger(__name__)

router = APIRouter()

# Scanner coverage categories and their expected scanners
_COVERAGE_CATEGORIES: dict[str, list[str]] = {
    "Network Intelligence": ["dns_recon", "shodan", "shodan_bulk", "cert_transparency",
                              "subdomain_enum", "ssl_scan", "http_fingerprint"],
    "Identity & Social": ["email_breach", "hibp", "username_scanner", "discord",
                           "github", "twitter", "linkedin", "fediverse_deep"],
    "Dark Web": ["darkweb_forum", "paste_monitor", "leaked_creds"],
    "Financial": ["crypto_clustering", "iban", "sec_edgar"],
    "Corporate Intelligence": ["job_intel", "whois_history", "brand_impersonation",
                                "news_media", "domain_whois"],
    "Threat Intelligence": ["virustotal", "malware_hash", "exploit_intel",
                             "ransomware_tracker"],
    "Person OSINT": ["people_search", "court_records", "academic", "patent",
                     "dating_app", "phone_cnam"],
}


class CoverageGap(BaseModel):
    category: str
    missing_scanners: list[str]
    coverage_percent: float
    recommendation: str


class CompletenessResponse(BaseModel):
    investigation_id: str
    overall_score: float
    grade: str
    categories_covered: int
    total_categories: int
    scanners_run: list[str]
    coverage_gaps: list[CoverageGap]
    recommendations: list[str]


@router.get("/investigations/{investigation_id}/completeness",
            response_model=CompletenessResponse, tags=["investigation-completeness"])
async def get_completeness_score(
    investigation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> CompletenessResponse:
    """Calculate investigation completeness score and surface coverage gaps."""

    result = await db.execute(
        select(ScanResultModel.scanner_name).where(
            ScanResultModel.investigation_id == investigation_id
        )
    )
    scanner_names = {row[0] for row in result.all() if row[0]}

    if not scanner_names:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="No scan results for this investigation")

    gaps: list[CoverageGap] = []
    category_scores: list[float] = []

    for category, expected in _COVERAGE_CATEGORIES.items():
        covered = [s for s in expected if any(s in sn for sn in scanner_names)]
        missing = [s for s in expected if not any(s in sn for sn in scanner_names)]
        pct = len(covered) / len(expected) if expected else 1.0
        category_scores.append(pct)

        if missing:
            gaps.append(CoverageGap(
                category=category,
                missing_scanners=missing[:5],
                coverage_percent=round(pct * 100, 1),
                recommendation=f"Run {', '.join(missing[:3])} scanner(s) to improve {category} coverage",
            ))

    overall = sum(category_scores) / len(category_scores) if category_scores else 0.0
    fully_covered = sum(1 for s in category_scores if s >= 0.5)

    grade = "A" if overall >= 0.85 else ("B" if overall >= 0.70 else
            ("C" if overall >= 0.55 else ("D" if overall >= 0.40 else "F")))

    recommendations = [g.recommendation for g in sorted(gaps, key=lambda x: x.coverage_percent)[:5]]

    return CompletenessResponse(
        investigation_id=investigation_id,
        overall_score=round(overall * 100, 1),
        grade=grade,
        categories_covered=fully_covered,
        total_categories=len(_COVERAGE_CATEGORIES),
        scanners_run=sorted(scanner_names)[:50],
        coverage_gaps=gaps,
        recommendations=recommendations,
    )
