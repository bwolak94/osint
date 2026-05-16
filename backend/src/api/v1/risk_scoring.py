"""Risk scoring engine — computes a composite threat/risk score for investigations."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.auth.dependencies import get_current_user
from src.dependencies import get_db

router = APIRouter(prefix="/risk-scoring", tags=["risk-scoring"])


# ---------------------------------------------------------------------------
# Severity weights used for risk calculation
# ---------------------------------------------------------------------------
_SEVERITY_WEIGHT: dict[str, float] = {
    "critical": 10.0,
    "high": 5.0,
    "medium": 2.0,
    "low": 1.0,
    "info": 0.1,
}

# Category multipliers — certain finding types are more significant
_CATEGORY_MULTIPLIERS: dict[str, float] = {
    "credentials_found": 2.5,
    "stealer_log_found": 3.0,
    "court_records_found": 2.0,
    "ofac_sanctions_hit": 4.0,
    "opensanctions_hit": 3.5,
    "malware_found": 2.5,
    "ransomware_victim": 3.0,
    "critical_cve": 2.0,
    "data_breach": 2.0,
    "dark_web_mention": 2.5,
    "domain_spoofing": 1.5,
}


class RiskScoreRequest(BaseModel):
    findings: list[dict[str, Any]]
    scan_results: list[dict[str, Any]] | None = None


class RiskScoreResponse(BaseModel):
    score: float  # 0-100
    risk_level: str  # LOW / MEDIUM / HIGH / CRITICAL
    breakdown: dict[str, Any]
    top_threats: list[dict[str, Any]]
    recommendations: list[str]


def _compute_risk_score(findings: list[dict[str, Any]]) -> RiskScoreResponse:
    """Compute a 0-100 risk score from a list of scan findings."""
    if not findings:
        return RiskScoreResponse(
            score=0.0,
            risk_level="LOW",
            breakdown={"total_findings": 0},
            top_threats=[],
            recommendations=["No findings — continue monitoring"],
        )

    raw_score: float = 0.0
    severity_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    top_threats: list[dict[str, Any]] = []

    for finding in findings:
        severity = finding.get("severity", "info").lower()
        finding_type = finding.get("type", "")
        source = finding.get("source", "")

        weight = _SEVERITY_WEIGHT.get(severity, 0.1)
        multiplier = _CATEGORY_MULTIPLIERS.get(finding_type, 1.0)

        contribution = weight * multiplier
        raw_score += contribution

        severity_counts[severity] = severity_counts.get(severity, 0) + 1
        type_counts[finding_type] = type_counts.get(finding_type, 0) + 1

        if severity in ("critical", "high") or multiplier >= 2.0:
            top_threats.append({
                "type": finding_type,
                "severity": severity,
                "source": source,
                "description": finding.get("description", ""),
                "contribution": round(contribution, 2),
            })

    # Normalize to 0-100 scale (logarithmic to prevent outliers)
    import math
    normalized = min(100.0, (math.log1p(raw_score) / math.log1p(200)) * 100)
    score = round(normalized, 1)

    # Risk level thresholds
    if score >= 80:
        risk_level = "CRITICAL"
    elif score >= 60:
        risk_level = "HIGH"
    elif score >= 30:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    # Sort top threats by contribution descending
    top_threats.sort(key=lambda x: x["contribution"], reverse=True)

    # Generate recommendations
    recommendations: list[str] = []
    if severity_counts.get("critical", 0) > 0:
        recommendations.append("IMMEDIATE: Critical findings require immediate investigation and remediation")
    if type_counts.get("credentials_found", 0) > 0 or type_counts.get("stealer_log_found", 0) > 0:
        recommendations.append("Change all passwords and enable MFA on all accounts immediately")
    if type_counts.get("court_records_found", 0) > 0:
        recommendations.append("Review legal history for potential fraud or criminal activity")
    if type_counts.get("ofac_sanctions_hit", 0) + type_counts.get("opensanctions_hit", 0) > 0:
        recommendations.append("CRITICAL: Subject appears on sanctions lists — consult legal counsel")
    if type_counts.get("dark_web_mention", 0) > 0:
        recommendations.append("Monitor dark web for further data exposure")
    if score >= 60:
        recommendations.append("Conduct thorough due diligence before any business engagement")
    if not recommendations:
        recommendations.append("Continue periodic monitoring; no immediate action required")

    return RiskScoreResponse(
        score=score,
        risk_level=risk_level,
        breakdown={
            "total_findings": len(findings),
            "severity_counts": severity_counts,
            "type_counts": type_counts,
            "raw_score": round(raw_score, 2),
        },
        top_threats=top_threats[:10],
        recommendations=recommendations,
    )


@router.post("/compute", response_model=RiskScoreResponse)
async def compute_risk_score(
    request: RiskScoreRequest,
    current_user: Any = Depends(get_current_user),
) -> RiskScoreResponse:
    """Compute a composite risk score from findings."""
    return _compute_risk_score(request.findings)


@router.get("/investigation/{investigation_id}", response_model=RiskScoreResponse)
async def get_investigation_risk_score(
    investigation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> RiskScoreResponse:
    """Compute risk score for an existing investigation's scan results."""
    from sqlalchemy import select, text
    from src.adapters.db.models import InvestigationModel, ScanResultModel

    # Load investigation and verify ownership
    inv = await db.get(InvestigationModel, investigation_id)
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investigation not found")

    if str(inv.owner_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # Aggregate findings from all scan results
    result = await db.execute(
        select(ScanResultModel).where(ScanResultModel.investigation_id == investigation_id)
    )
    scan_results = result.scalars().all()

    all_findings: list[dict[str, Any]] = []
    for sr in scan_results:
        raw = sr.raw_output or {}
        findings = raw.get("findings", [])
        all_findings.extend(findings)

    return _compute_risk_score(all_findings)
