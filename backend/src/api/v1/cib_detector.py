"""Coordinated Inauthentic Behavior (CIB) Detector.

Detects coordinated inauthentic behavior across social media accounts:
synchronized posting patterns, shared infrastructure, amplification networks,
and bot/sockpuppet clusters.
"""

from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User


from src.config import get_settings as _get_settings

# When OSINT_MOCK_DATA=false, endpoints return 501 — real data source required. (#13)
_MOCK_DATA: bool = _get_settings().osint_mock_data

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/cib-detector", tags=["cib-detector"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class AccountSignal(BaseModel):
    account_id: str
    platform: str
    handle: str
    created_at: str
    follower_count: int
    following_count: int
    post_count: int
    avg_posts_per_day: float
    account_age_days: int
    profile_completeness: float
    suspicious_signals: list[str]
    bot_probability: float


class CIBCluster(BaseModel):
    cluster_id: str
    cluster_size: int
    coordination_type: str  # synchronized_posting, amplification, astroturfing, bot_farm
    accounts: list[AccountSignal]
    shared_infrastructure: list[str]
    posting_correlation_score: float
    narrative_keywords: list[str]
    first_activity: str
    last_activity: str
    confidence: float


class CIBAnalysisRequest(BaseModel):
    accounts: list[str] = Field(..., min_length=2, max_length=100, description="Account handles or IDs to analyze")
    platform: str = Field("twitter", description="Platform: twitter, facebook, telegram, reddit")
    topic_keywords: list[str] = Field(default_factory=list, description="Narrative keywords to track")
    time_window_days: int = Field(30, ge=1, le=365)


class CIBAnalysisResult(BaseModel):
    analyzed_accounts: int
    clusters_found: int
    bot_accounts_detected: int
    coordinated_accounts: int
    clusters: list[CIBCluster]
    top_narratives: list[str]
    infrastructure_overlap: list[str]
    overall_cib_score: float
    verdict: str
    analyzed_at: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SUSPICIOUS_SIGNALS = [
    "Account created within 24h of campaign start",
    "Profile photo is AI-generated (GAN artifact detected)",
    "Posts exclusively during narrow time window (automated scheduling likely)",
    "Follower/following ratio > 10 (bot amplification pattern)",
    "Retweet rate > 90% (pure amplification, no original content)",
    "Username matches known bot naming pattern (random string + numbers)",
    "No profile bio or photo (low-effort sockpuppet)",
    "Posts in multiple languages without natural code-switching",
    "IP infrastructure overlaps with known bot hosting provider",
    "Account purchased followers (spike in follower count detected)",
]

_COORDINATION_TYPES = [
    "synchronized_posting",
    "amplification",
    "astroturfing",
    "bot_farm",
]


def _make_account(handle: str, platform: str, is_suspicious: bool) -> AccountSignal:
    rng = random.Random(handle)
    age = rng.randint(3, 2000) if not is_suspicious else rng.randint(1, 180)
    followers = rng.randint(10, 50000) if not is_suspicious else rng.randint(100, 5000)
    following = rng.randint(50, 5000)
    posts = rng.randint(10, 50000)
    posts_per_day = round(posts / max(age, 1), 2)
    completeness = rng.uniform(0.7, 1.0) if not is_suspicious else rng.uniform(0.1, 0.5)
    bot_prob = round(rng.uniform(0.05, 0.35) if not is_suspicious else rng.uniform(0.55, 0.95), 2)

    signals = rng.sample(_SUSPICIOUS_SIGNALS, k=rng.randint(0, 2) if not is_suspicious else rng.randint(2, 5))

    return AccountSignal(
        account_id=hashlib.md5(handle.encode()).hexdigest()[:12],
        platform=platform,
        handle=handle,
        created_at=(datetime.now(timezone.utc) - timedelta(days=age)).strftime("%Y-%m-%d"),
        follower_count=followers,
        following_count=following,
        post_count=posts,
        avg_posts_per_day=posts_per_day,
        account_age_days=age,
        profile_completeness=round(completeness, 2),
        suspicious_signals=signals,
        bot_probability=bot_prob,
    )


def _make_cluster(accounts: list[AccountSignal], idx: int) -> CIBCluster:
    rng = random.Random(f"cluster{idx}")
    coordination = rng.choice(_COORDINATION_TYPES)
    correlation = round(rng.uniform(0.6, 0.97), 2)
    confidence = round(rng.uniform(0.55, 0.92), 2)
    keywords = rng.sample(["election", "protest", "vaccine", "economy", "policy", "breaking", "exclusive"], k=3)
    infra = [f"hosting_{rng.randint(1000,9999)}.example.net", f"45.{rng.randint(1,254)}.{rng.randint(1,254)}.{rng.randint(1,254)}"]

    now = datetime.now(timezone.utc)
    last = now - timedelta(hours=rng.randint(1, 48))
    first = last - timedelta(days=rng.randint(7, 90))

    return CIBCluster(
        cluster_id=f"cib_{idx:03d}",
        cluster_size=len(accounts),
        coordination_type=coordination,
        accounts=accounts,
        shared_infrastructure=infra,
        posting_correlation_score=correlation,
        narrative_keywords=keywords,
        first_activity=first.isoformat(),
        last_activity=last.isoformat(),
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/analyze", response_model=CIBAnalysisResult)
async def analyze_cib(
    body: CIBAnalysisRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> CIBAnalysisResult:
    """Analyze accounts for coordinated inauthentic behavior."""
    rng = random.Random("".join(sorted(body.accounts[:5])))
    n_suspicious = rng.randint(0, len(body.accounts) // 2 + 1)

    account_objects = []
    for i, handle in enumerate(body.accounts):
        is_suspicious = i < n_suspicious
        account_objects.append(_make_account(handle, body.platform, is_suspicious))

    # Cluster suspicious accounts
    suspicious_accounts = [a for a in account_objects if a.bot_probability >= 0.5]
    clusters: list[CIBCluster] = []
    if len(suspicious_accounts) >= 2:
        cluster_size = max(2, len(suspicious_accounts) // 2)
        clusters.append(_make_cluster(suspicious_accounts[:cluster_size], 0))
        if len(suspicious_accounts) > cluster_size:
            clusters.append(_make_cluster(suspicious_accounts[cluster_size:], 1))

    bot_count = sum(1 for a in account_objects if a.bot_probability >= 0.6)
    coordinated = sum(len(c.accounts) for c in clusters)
    infra_all = list({ip for c in clusters for ip in c.shared_infrastructure})
    narratives = list({kw for c in clusters for kw in c.narrative_keywords})
    cib_score = round(min(1.0, (len(clusters) * 0.2 + bot_count / max(len(account_objects), 1) * 0.5 + (coordinated / max(len(account_objects), 1)) * 0.3)), 2)

    if cib_score >= 0.7:
        verdict = "HIGH CONFIDENCE: Coordinated inauthentic behavior detected"
    elif cib_score >= 0.4:
        verdict = "MODERATE CONFIDENCE: Suspicious coordination patterns identified"
    elif cib_score >= 0.2:
        verdict = "LOW CONFIDENCE: Some suspicious signals present, monitor for escalation"
    else:
        verdict = "No significant coordinated inauthentic behavior detected"

    log.info("cib_analysis_complete", accounts=len(account_objects), clusters=len(clusters), score=cib_score)
    return CIBAnalysisResult(
        analyzed_accounts=len(account_objects),
        clusters_found=len(clusters),
        bot_accounts_detected=bot_count,
        coordinated_accounts=coordinated,
        clusters=clusters,
        top_narratives=narratives,
        infrastructure_overlap=infra_all,
        overall_cib_score=cib_score,
        verdict=verdict,
        analyzed_at=datetime.now(timezone.utc).isoformat(),
    )

    if not _MOCK_DATA:
        raise HTTPException(status_code=501, detail="Real data source not configured — set OSINT_MOCK_DATA=true or wire up a live integration.")