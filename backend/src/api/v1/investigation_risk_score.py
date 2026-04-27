"""Investigation risk score endpoint — computes and caches a 0-100 risk score."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.database import async_session_factory
from src.adapters.db.models import (
    IdentityModel,
    InvestigationModel,
    InvestigationRiskScoreModel,
    ScanResultModel,
)
from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.types import ScanStatus
from src.core.domain.entities.user import User
from src.utils.time import utcnow

router = APIRouter()


class RiskFactor(BaseModel):
    """A single scored factor contributing to the overall risk score."""
    name: str
    score: float
    weight: float          # proportion of this factor in the total (0.0–1.0)
    description: str
    raw_value: Any         # the raw metric (breach count, port count, etc.)


class RiskScoreResponse(BaseModel):
    model_config = {"json_schema_extra": {"example": {
        "investigation_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "score": 67.5,
        "label": "high",
        "breach_count": 3,
        "exposed_services": 8,
        "avg_confidence": 0.82,
        "factors": {"breach": 30, "exposed_services": 24, "avg_confidence": 13},
        "factor_breakdown": [],
        "top_contributing_factor": "breach",
        "computed_at": "2026-04-25T12:00:00.000Z",
    }}}

    investigation_id: str
    score: float
    label: str  # "low" | "medium" | "high" | "critical"
    breach_count: int
    exposed_services: int
    avg_confidence: float
    factors: dict[str, Any]
    factor_breakdown: list[RiskFactor] = []
    top_contributing_factor: str | None = None
    computed_at: str


def _label(score: float) -> str:
    if score < 25:
        return "low"
    if score < 50:
        return "medium"
    if score < 75:
        return "high"
    return "critical"


async def _compute_risk_score(
    investigation_id: uuid.UUID,
    db: AsyncSession,
) -> InvestigationRiskScoreModel:
    """Compute the risk score from current scan results and identities."""

    scan_stmt = select(ScanResultModel).where(
        ScanResultModel.investigation_id == investigation_id
    )
    scan_results = (await db.execute(scan_stmt)).scalars().all()

    identity_stmt = select(IdentityModel).where(
        IdentityModel.investigation_id == investigation_id
    )
    identities = (await db.execute(identity_stmt)).scalars().all()

    # Count breach-related results
    breach_count = sum(
        1 for r in scan_results
        if r.scanner_name in ("breach_scanner", "h8mail_scanner", "pwndb_scanner", "holehe_scanner")
        and r.status == ScanStatus.SUCCESS
        and r.raw_data
    )

    # Count exposed services (Shodan / nmap / nuclei results)
    exposed_services = sum(
        len(r.raw_data.get("ports", r.raw_data.get("hosts", [])))
        for r in scan_results
        if r.scanner_name in ("shodan_scanner", "nuclei_scanner", "banner_grabber_scanner")
        and r.status == ScanStatus.SUCCESS
    )

    # Average identity confidence
    avg_confidence = (
        sum(i.confidence_score for i in identities) / len(identities)
        if identities
        else 0.0
    )

    # Failed / rate-limited scans reduce confidence in completeness
    total = len(scan_results)
    failed = sum(1 for r in scan_results if r.status == ScanStatus.FAILED)
    completeness_penalty = (failed / total * 10) if total > 0 else 0

    factors: dict[str, Any] = {
        "breach_score": min(breach_count * 15, 40),
        "exposure_score": min(exposed_services * 2, 30),
        "confidence_score": avg_confidence * 20,
        "completeness_penalty": completeness_penalty,
    }

    score = min(
        factors["breach_score"]
        + factors["exposure_score"]
        + factors["confidence_score"]
        - factors["completeness_penalty"],
        100.0,
    )
    score = max(score, 0.0)

    # Upsert risk score
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    stmt = (
        pg_insert(InvestigationRiskScoreModel)
        .values(
            id=uuid.uuid4(),
            investigation_id=investigation_id,
            score=score,
            breach_count=breach_count,
            exposed_services=exposed_services,
            avg_confidence=avg_confidence,
            factors=factors,
            computed_at=utcnow(),
        )
        .on_conflict_do_update(
            index_elements=["investigation_id"],
            set_={
                "score": score,
                "breach_count": breach_count,
                "exposed_services": exposed_services,
                "avg_confidence": avg_confidence,
                "factors": factors,
                "computed_at": utcnow(),
            },
        )
    )
    await db.execute(stmt)
    await db.commit()

    row_stmt = select(InvestigationRiskScoreModel).where(
        InvestigationRiskScoreModel.investigation_id == investigation_id
    )
    return (await db.execute(row_stmt)).scalar_one()


@router.get(
    "/investigations/{investigation_id}/risk-score",
    response_model=RiskScoreResponse,
    tags=["risk-score"],
)
async def get_risk_score(
    investigation_id: str,
    recompute: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(lambda: async_session_factory()),
) -> RiskScoreResponse:
    """Return (and optionally recompute) the risk score for an investigation."""
    inv_id = uuid.UUID(investigation_id)

    inv = (
        await db.execute(select(InvestigationModel).where(InvestigationModel.id == inv_id))
    ).scalar_one_or_none()
    if inv is None:
        raise HTTPException(status_code=404, detail="Investigation not found")

    if not recompute:
        cached_stmt = select(InvestigationRiskScoreModel).where(
            InvestigationRiskScoreModel.investigation_id == inv_id
        )
        cached = (await db.execute(cached_stmt)).scalar_one_or_none()
        if cached is not None:
            return _build_response(investigation_id, cached)

    row = await _compute_risk_score(inv_id, db)
    return _build_response(investigation_id, row)


def _build_factor_breakdown(factors: dict[str, Any], total_score: float) -> tuple[list[RiskFactor], str | None]:
    """Convert raw factor dict into descriptive RiskFactor objects."""
    definitions = {
        "breach_score": ("Credential Breaches", "Number of data breach hits from HIBP/pwndb/holehe scanners"),
        "exposure_score": ("Exposed Services", "Open ports and vulnerable services found via Shodan/Nuclei"),
        "confidence_score": ("Identity Confidence", "Average confidence of resolved identity records"),
        "completeness_penalty": ("Scan Completeness Penalty", "Deduction for failed scanner runs reducing data coverage"),
    }
    breakdown: list[RiskFactor] = []
    for key, value in factors.items():
        name, description = definitions.get(key, (key.replace("_", " ").title(), ""))
        weight = abs(float(value)) / max(total_score, 1.0)
        raw_map = {
            "breach_score": factors.get("breach_score"),
            "exposure_score": factors.get("exposure_score"),
            "confidence_score": factors.get("confidence_score"),
        }
        breakdown.append(RiskFactor(
            name=name,
            score=round(float(value), 2),
            weight=round(weight, 4),
            description=description,
            raw_value=raw_map.get(key, value),
        ))
    # Sort descending by absolute contribution
    breakdown.sort(key=lambda f: abs(f.score), reverse=True)
    top = breakdown[0].name if breakdown else None
    return breakdown, top


def _build_response(investigation_id: str, row: Any) -> RiskScoreResponse:
    breakdown, top = _build_factor_breakdown(row.factors, row.score)
    return RiskScoreResponse(
        investigation_id=investigation_id,
        score=row.score,
        label=_label(row.score),
        breach_count=row.breach_count,
        exposed_services=row.exposed_services,
        avg_confidence=row.avg_confidence,
        factors=row.factors,
        factor_breakdown=breakdown,
        top_contributing_factor=top,
        computed_at=row.computed_at.isoformat(),
    )
