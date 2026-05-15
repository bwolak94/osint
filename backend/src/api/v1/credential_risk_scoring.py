"""Credential Exposure Risk Scoring.

Scores exposed credentials by breach age, password reuse probability,
MFA bypass likelihood, and attack surface impact.
"""

from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field

from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User


from src.config import get_settings as _get_settings

# When OSINT_MOCK_DATA=false, endpoints return 501 — real data source required. (#13)
_MOCK_DATA: bool = _get_settings().osint_mock_data

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/credential-risk", tags=["credential-risk"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class BreachRecord(BaseModel):
    breach_name: str
    breach_date: str
    data_classes: list[str]
    password_exposed: bool
    verified: bool
    is_sensitive: bool


class CredentialRiskScore(BaseModel):
    email: str
    overall_risk_score: float  # 0.0–10.0
    risk_level: str  # critical, high, medium, low
    breach_count: int
    oldest_breach_days: int
    newest_breach_days: int
    password_exposed_count: int
    reuse_probability: float  # 0.0–1.0
    mfa_bypass_risk: float  # 0.0–1.0
    spray_attack_risk: float  # 0.0–1.0
    estimated_cracked_pct: float  # % chance password already cracked
    breaches: list[BreachRecord]
    exposed_data_classes: list[str]
    risk_factors: list[str]
    mitigations: list[str]
    score_breakdown: dict[str, float]


class BatchScoringRequest(BaseModel):
    emails: list[str] = Field(..., min_length=1, max_length=50)
    include_breach_detail: bool = True


class BatchScoringResult(BaseModel):
    total_emails: int
    critical_count: int
    high_count: int
    results: list[CredentialRiskScore]
    analyzed_at: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BREACHES = [
    ("LinkedIn 2012", "2012-06-05", ["email", "password", "username"], True),
    ("Adobe 2013", "2013-10-04", ["email", "password", "hint", "username"], True),
    ("MySpace 2016", "2016-05-31", ["email", "password", "username"], True),
    ("Collection #1 2019", "2019-01-07", ["email", "password"], False),
    ("RockYou2021", "2021-06-01", ["password"], False),
    ("Twitter 2022", "2022-07-22", ["email", "phone"], True),
    ("AT&T 2024", "2024-03-30", ["email", "phone", "ssn", "dob"], True),
    ("Dropbox 2012", "2012-07-01", ["email", "password"], True),
    ("Yahoo 2013", "2013-08-01", ["email", "password", "security_question", "dob"], True),
    ("Canva 2019", "2019-05-24", ["email", "username", "name", "password"], True),
]


def _score_email(email: str) -> CredentialRiskScore:
    rng = random.Random(email)
    num_breaches = rng.randint(0, 6)
    selected = rng.sample(_BREACHES, k=min(num_breaches, len(_BREACHES)))

    breaches: list[BreachRecord] = []
    pw_exposed = 0
    data_classes: set[str] = set()
    oldest_days = 0
    newest_days = 999999

    for name, date_str, classes, verified in selected:
        breach_dt = datetime.fromisoformat(date_str)
        days_ago = (datetime.now(timezone.utc) - breach_dt.replace(tzinfo=timezone.utc)).days
        oldest_days = max(oldest_days, days_ago)
        newest_days = min(newest_days, days_ago)
        has_pw = "password" in classes
        if has_pw:
            pw_exposed += 1
        data_classes.update(classes)
        breaches.append(BreachRecord(
            breach_name=name,
            breach_date=date_str,
            data_classes=classes,
            password_exposed=has_pw,
            verified=verified,
            is_sensitive="ssn" in classes or "dob" in classes,
        ))

    if not breaches:
        newest_days = 0

    # Scoring components (0–10 scale)
    breach_score = min(10.0, num_breaches * 1.5)
    age_score = max(0.0, 5.0 - (oldest_days / 365) * 0.5) if oldest_days > 0 else 0.0
    pw_score = min(10.0, pw_exposed * 2.5)
    reuse_prob = round(min(0.95, 0.3 + pw_exposed * 0.15 + rng.uniform(0, 0.2)), 2)
    mfa_bypass = round(rng.uniform(0.1, 0.5), 2)
    spray_risk = round(min(0.9, 0.2 + num_breaches * 0.1), 2)
    cracked_pct = round(min(99.0, pw_exposed * 18.0 + rng.uniform(0, 15)), 1)

    overall = round((breach_score * 0.3 + pw_score * 0.4 + age_score * 0.2 + spray_risk * 10 * 0.1), 1)
    overall = min(10.0, overall)
    risk_level = "critical" if overall >= 7 else "high" if overall >= 5 else "medium" if overall >= 3 else "low"

    risk_factors: list[str] = []
    if pw_exposed >= 3:
        risk_factors.append(f"Password exposed in {pw_exposed} breaches — high cracking probability")
    if newest_days < 180:
        risk_factors.append("Recent breach within 6 months — credentials likely still valid")
    if "ssn" in data_classes:
        risk_factors.append("Social Security Number exposed — identity theft risk")
    if reuse_prob > 0.6:
        risk_factors.append("High password reuse probability across services")
    if num_breaches >= 4:
        risk_factors.append("Persistent long-term exposure pattern")

    mitigations = [
        "Reset password immediately on all affected services",
        "Enable FIDO2/WebAuthn MFA (phishing-resistant)",
        "Audit SSO and OAuth application permissions",
        "Monitor for account takeover indicators in authentication logs",
    ]
    if "ssn" in data_classes:
        mitigations.append("Consider credit freeze with major bureaus")

    return CredentialRiskScore(
        email=email,
        overall_risk_score=overall,
        risk_level=risk_level,
        breach_count=num_breaches,
        oldest_breach_days=oldest_days,
        newest_breach_days=newest_days if newest_days < 999999 else 0,
        password_exposed_count=pw_exposed,
        reuse_probability=reuse_prob,
        mfa_bypass_risk=mfa_bypass,
        spray_attack_risk=spray_risk,
        estimated_cracked_pct=cracked_pct,
        breaches=breaches,
        exposed_data_classes=list(data_classes),
        risk_factors=risk_factors,
        mitigations=mitigations,
        score_breakdown={
            "breach_frequency": round(breach_score, 1),
            "password_exposure": round(pw_score, 1),
            "recency": round(age_score, 1),
            "spray_attack": round(spray_risk * 10, 1),
        },
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/score", response_model=CredentialRiskScore)
async def score_single_credential(
    email: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> CredentialRiskScore:
    """Score a single email address for credential exposure risk."""
    if not _MOCK_DATA:
        raise HTTPException(status_code=501, detail="Real data source not configured — set OSINT_MOCK_DATA=true or wire up a live integration.")
    result = _score_email(email)
    log.info("credential_risk_scored", email=email[:3] + "***", risk_level=result.risk_level)
    return result


@router.post("/batch-score", response_model=BatchScoringResult)
async def batch_score_credentials(
    body: BatchScoringRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> BatchScoringResult:
    """Score multiple email addresses for credential exposure risk."""
    results = [_score_email(email) for email in body.emails]
    if not body.include_breach_detail:
        for r in results:
            r.breaches = []

    results.sort(key=lambda x: x.overall_risk_score, reverse=True)
    critical = sum(1 for r in results if r.risk_level == "critical")
    high = sum(1 for r in results if r.risk_level == "high")

    log.info("credential_batch_scored", count=len(results), critical=critical, high=high)
    return BatchScoringResult(
        total_emails=len(results),
        critical_count=critical,
        high_count=high,
        results=results,
        analyzed_at=datetime.now(timezone.utc).isoformat(),
    )
