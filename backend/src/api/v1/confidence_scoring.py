"""Per-finding confidence scoring endpoint.

POST /api/v1/confidence/score — score a batch of findings
GET  /api/v1/confidence/investigation/{id} — get confidence breakdown for all findings
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

# Source reliability weights (0.0–1.0)
_SOURCE_WEIGHTS: dict[str, float] = {
    "shodan": 0.95,
    "virustotal": 0.95,
    "hibp": 0.95,
    "nhtsa": 0.95,
    "sec_edgar": 0.90,
    "crt.sh": 0.90,
    "nist": 0.90,
    "censys": 0.90,
    "blockchair": 0.85,
    "whois": 0.85,
    "github": 0.85,
    "linkedin": 0.80,
    "twitter": 0.75,
    "ahmia": 0.70,
    "darksearch": 0.65,
    "peoples_search": 0.50,
    "indeed": 0.60,
    "default": 0.70,
}

# Finding type multipliers
_TYPE_MULTIPLIERS: dict[str, float] = {
    "vin_decoded": 1.0,
    "crypto_address_stats": 1.0,
    "data_breach": 1.0,
    "cve": 0.95,
    "ip_enrichment": 0.90,
    "domain_whois": 0.90,
    "certificate_transparency": 0.88,
    "social_profile": 0.75,
    "job_postings_found": 0.65,
    "darkweb_mention": 0.60,
    "people_search_results": 0.50,
    "default": 0.75,
}

_CORROBORATION_BONUS = 0.05  # per additional source confirming same finding type


class FindingScore(BaseModel):
    finding_type: str
    source: str
    severity: str
    base_confidence: float
    source_weight: float
    type_multiplier: float
    final_confidence: float
    confidence_label: str


class ConfidenceResponse(BaseModel):
    investigation_id: str | None
    scored_findings: list[FindingScore]
    average_confidence: float
    high_confidence_count: int
    low_confidence_count: int


def _score_finding(finding: dict[str, Any], corroboration_count: int = 1) -> FindingScore:
    ftype = finding.get("type", "default")
    source = (finding.get("source") or "default").lower()

    source_weight = _SOURCE_WEIGHTS.get(source, _SOURCE_WEIGHTS["default"])
    type_mult = _TYPE_MULTIPLIERS.get(ftype, _TYPE_MULTIPLIERS["default"])

    # Severity bonus
    sev = finding.get("severity", "info")
    sev_bonus = {"critical": 0.05, "high": 0.03, "medium": 0.01, "low": 0.0, "info": 0.0}.get(sev, 0.0)

    # Corroboration bonus (capped at 3 sources)
    corr_bonus = min(corroboration_count - 1, 3) * _CORROBORATION_BONUS

    raw = (source_weight * type_mult) + sev_bonus + corr_bonus
    final = round(min(1.0, max(0.0, raw)), 3)

    if final >= 0.85:
        label = "very_high"
    elif final >= 0.70:
        label = "high"
    elif final >= 0.55:
        label = "medium"
    elif final >= 0.40:
        label = "low"
    else:
        label = "very_low"

    return FindingScore(
        finding_type=ftype,
        source=finding.get("source", "unknown"),
        severity=sev,
        base_confidence=round(source_weight * type_mult, 3),
        source_weight=source_weight,
        type_multiplier=type_mult,
        final_confidence=final,
        confidence_label=label,
    )


@router.get("/confidence/investigation/{investigation_id}",
            response_model=ConfidenceResponse, tags=["confidence"])
async def get_investigation_confidence(
    investigation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> ConfidenceResponse:
    """Return per-finding confidence scores for all findings in an investigation."""

    result = await db.execute(
        select(ScanResultModel).where(
            ScanResultModel.investigation_id == investigation_id
        ).limit(200)
    )
    scan_results = result.scalars().all()
    if not scan_results:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="No scan results for this investigation")

    # Count corroboration: how many scanners report same finding type
    type_counts: dict[str, int] = {}
    for sr in scan_results:
        for f in (sr.raw_data or {}).get("findings", []):
            ftype = f.get("type", "unknown")
            type_counts[ftype] = type_counts.get(ftype, 0) + 1

    scored: list[FindingScore] = []
    for sr in scan_results:
        for f in (sr.raw_data or {}).get("findings", []):
            corr = type_counts.get(f.get("type", ""), 1)
            scored.append(_score_finding(f, corr))

    if not scored:
        return ConfidenceResponse(
            investigation_id=investigation_id,
            scored_findings=[],
            average_confidence=0.0,
            high_confidence_count=0,
            low_confidence_count=0,
        )

    avg = round(sum(s.final_confidence for s in scored) / len(scored), 3)
    high_count = sum(1 for s in scored if s.final_confidence >= 0.70)
    low_count = sum(1 for s in scored if s.final_confidence < 0.55)

    return ConfidenceResponse(
        investigation_id=investigation_id,
        scored_findings=scored[:100],
        average_confidence=avg,
        high_confidence_count=high_count,
        low_confidence_count=low_count,
    )
