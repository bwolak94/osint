"""Attack surface scoring for investigations."""

import re
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.database import get_db
from src.adapters.db.models import InvestigationModel, ScanResultModel, UserModel
from src.api.v1.auth.dependencies import get_current_user

log = structlog.get_logger(__name__)

router = APIRouter()

_PORT_PATTERN = re.compile(r"\bport\b", re.IGNORECASE)
_CVE_PATTERN = re.compile(r"\bCVE-\d{4}-\d+\b", re.IGNORECASE)
_SERVICE_PATTERN = re.compile(r"\b(service|port|banner)\b", re.IGNORECASE)
_SSL_PATTERN = re.compile(r"\b(ssl|tls|certificate)\b.*\b(error|issue|expired|invalid|weak)\b", re.IGNORECASE)
_CLOUD_PATTERN = re.compile(r"\b(misconfigur|s3.*public|bucket.*open|storage.*exposed|open.*bucket)\b", re.IGNORECASE)
_DEFAULT_CREDS_PATTERN = re.compile(r"\b(default.credenti|admin:admin|admin:password|root:root)\b", re.IGNORECASE)
_SUBDOMAIN_PATTERN = re.compile(r"\bsubdomain\b", re.IGNORECASE)


def _findings_to_text(findings: Any) -> str:
    """Flatten findings dict/list to a searchable text blob."""
    if isinstance(findings, str):
        return findings
    if isinstance(findings, dict):
        return " ".join(str(v) for v in findings.values())
    if isinstance(findings, list):
        return " ".join(str(item) for item in findings)
    return str(findings) if findings else ""


def _count_open_ports(text: str) -> int:
    """Count open port references in findings text."""
    return len(re.findall(r"\bport\s+\d+\b.*?\bopen\b|\bopen\b.*?\bport\s+\d+\b", text, re.IGNORECASE))


def _count_cves(text: str) -> int:
    return len(_CVE_PATTERN.findall(text))


def _count_exposed_services(text: str) -> int:
    return len(_SERVICE_PATTERN.findall(text))


def _count_subdomains(findings: Any) -> int:
    """Count distinct subdomain entries."""
    if not isinstance(findings, dict):
        return 0
    subdomains = findings.get("subdomains", findings.get("subdomain_list", []))
    if isinstance(subdomains, list):
        return len(subdomains)
    return 0


def _count_ssl_issues(text: str) -> int:
    return len(_SSL_PATTERN.findall(text))


def _count_cloud_misconfigs(text: str) -> int:
    return len(_CLOUD_PATTERN.findall(text))


def _has_default_creds(text: str) -> bool:
    return bool(_DEFAULT_CREDS_PATTERN.search(text))


def _score_to_grade(score: int) -> str:
    if score <= 20:
        return "A"
    if score <= 40:
        return "B"
    if score <= 60:
        return "C"
    if score <= 80:
        return "D"
    return "F"


def _score_to_risk_level(score: int) -> str:
    if score <= 20:
        return "low"
    if score <= 50:
        return "medium"
    if score <= 75:
        return "high"
    return "critical"


class AttackSurfaceScore(BaseModel):
    investigation_id: str
    score: int
    grade: str
    risk_level: str
    breakdown: dict[str, int]
    top_risks: list[str]
    recommendations: list[str]
    total_findings_analyzed: int


@router.get(
    "/investigations/{investigation_id}/attack-surface-score",
    response_model=AttackSurfaceScore,
    tags=["attack-surface-score"],
)
async def get_attack_surface_score(
    investigation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> AttackSurfaceScore:
    """Score the attack surface of an investigation based on its findings."""
    inv_result = await db.execute(
        select(InvestigationModel).where(InvestigationModel.id == investigation_id)
    )
    investigation = inv_result.scalar_one_or_none()
    if investigation is None:
        raise HTTPException(status_code=404, detail="Investigation not found")

    result = await db.execute(
        select(ScanResultModel)
        .where(ScanResultModel.investigation_id == investigation_id)
        .limit(500)
    )
    scan_results = list(result.scalars().all())

    # Aggregate text and structured findings
    all_text_parts: list[str] = []
    total_subdomains = 0

    for sr in scan_results:
        text = _findings_to_text(sr.findings)
        all_text_parts.append(text)
        total_subdomains += _count_subdomains(sr.findings)

    combined_text = " ".join(all_text_parts)

    # Score each category
    open_ports = _count_open_ports(combined_text)
    cve_count = _count_cves(combined_text)
    exposed_services = _count_exposed_services(combined_text)
    ssl_issues = _count_ssl_issues(combined_text)
    cloud_misconfigs = _count_cloud_misconfigs(combined_text)
    default_creds = _has_default_creds(combined_text)

    ports_pts = min(open_ports * 2, 30)
    cve_pts = min(cve_count * 5, 40)
    services_pts = min(exposed_services * 3, 15)
    subdomain_pts = min(total_subdomains * 1, 10)
    ssl_pts = min(ssl_issues * 5, 25)
    cloud_pts = min(cloud_misconfigs * 8, 24)
    creds_pts = 15 if default_creds else 0

    raw_score = ports_pts + cve_pts + services_pts + subdomain_pts + ssl_pts + cloud_pts + creds_pts
    score = min(raw_score, 100)

    breakdown: dict[str, int] = {
        "open_ports": ports_pts,
        "cve_findings": cve_pts,
        "exposed_services": services_pts,
        "subdomains": subdomain_pts,
        "ssl_issues": ssl_pts,
        "cloud_misconfigs": cloud_pts,
        "default_credentials": creds_pts,
    }

    # Build top risks (categories with non-zero contribution, sorted descending)
    top_risks: list[str] = [
        k.replace("_", " ").title()
        for k, v in sorted(breakdown.items(), key=lambda x: -x[1])
        if v > 0
    ][:5]

    # Recommendations based on what was found
    recommendations: list[str] = []
    if open_ports > 0:
        recommendations.append("Review and close unnecessary open ports using firewall rules.")
    if cve_count > 0:
        recommendations.append(f"Patch or mitigate {cve_count} discovered CVE(s) immediately.")
    if ssl_issues > 0:
        recommendations.append("Renew or reconfigure SSL/TLS certificates to resolve issues.")
    if cloud_misconfigs > 0:
        recommendations.append("Audit cloud storage buckets and enforce access controls.")
    if default_creds:
        recommendations.append("Change all default credentials immediately — credential stuffing risk is critical.")
    if total_subdomains > 10:
        recommendations.append("Audit subdomain inventory and remove unused/dangling subdomains.")
    if not recommendations:
        recommendations.append("Attack surface appears minimal. Maintain regular scanning cadence.")

    grade = _score_to_grade(score)
    risk_level = _score_to_risk_level(score)

    log.info(
        "attack_surface_scored",
        investigation_id=investigation_id,
        score=score,
        grade=grade,
        risk_level=risk_level,
        total_findings=len(scan_results),
    )

    return AttackSurfaceScore(
        investigation_id=investigation_id,
        score=score,
        grade=grade,
        risk_level=risk_level,
        breakdown=breakdown,
        top_risks=top_risks,
        recommendations=recommendations,
        total_findings_analyzed=len(scan_results),
    )
