"""Behavioral pattern fingerprinting — infer behavioral patterns from OSINT findings.

POST /api/v1/behavioral/fingerprint/{investigation_id} — generate behavioral fingerprint
"""

from __future__ import annotations

import re
from collections import Counter
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

# Activity time patterns
_TIME_RE = re.compile(r'\b([01]?\d|2[0-3]):([0-5]\d)(?::[0-5]\d)?\b')
_DATE_RE = re.compile(r'(20\d{2})[-/](\d{2})[-/](\d{2})')

# Platform behavioral signals
_PLATFORM_SIGNALS: dict[str, list[str]] = {
    "developer": ["github", "gitlab", "stackoverflow", "npm", "pypi", "hackernews"],
    "researcher": ["orcid", "arxiv", "semantic_scholar", "academia", "researchgate"],
    "trader_crypto": ["blockchair", "walletexplorer", "blockchain.info", "binance"],
    "social_heavy": ["twitter", "instagram", "facebook", "tiktok", "snapchat"],
    "security_professional": ["shodan", "virustotal", "hackerone", "bugcrowd", "cve"],
    "corporate": ["linkedin", "glassdoor", "crunchbase", "sec_edgar"],
    "darkweb_actor": ["ahmia", "darksearch", "intelx", "tor"],
}


class BehavioralPattern(BaseModel):
    pattern_name: str
    confidence: float
    signals: list[str]
    description: str


class BehavioralFingerprint(BaseModel):
    investigation_id: str
    patterns: list[BehavioralPattern]
    primary_persona: str
    activity_hours: list[int]
    platform_footprint: list[str]
    linguistic_indicators: list[str]
    risk_profile: str
    summary: str


@router.post("/behavioral/fingerprint/{investigation_id}",
             response_model=BehavioralFingerprint, tags=["behavioral"])
async def generate_behavioral_fingerprint(
    investigation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> BehavioralFingerprint:
    """Generate a behavioral fingerprint from OSINT findings."""

    result = await db.execute(
        select(ScanResultModel).where(
            ScanResultModel.investigation_id == investigation_id
        ).limit(200)
    )
    scan_results = result.scalars().all()
    if not scan_results:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="No scan results for this investigation")

    scanners_hit: list[str] = []
    all_text = ""
    hours_found: list[int] = []
    platforms: set[str] = set()
    linguistic: list[str] = []

    for sr in scan_results:
        scanner = (sr.scanner_name or "").lower()
        scanners_hit.append(scanner)
        raw_text = str(sr.raw_data or {})
        all_text += " " + raw_text

        # Extract activity times
        for m in _TIME_RE.finditer(raw_text):
            hours_found.append(int(m.group(1)))

        # Platform presence
        findings = (sr.raw_data or {}).get("findings", [])
        for f in findings:
            src = (f.get("source") or "").lower()
            if src:
                platforms.add(src)
            # Language/style signals from bio/description
            desc = f.get("description") or f.get("bio") or ""
            if isinstance(desc, str) and len(desc) > 20:
                if re.search(r'\b(developer|engineer|hacker|researcher|analyst)\b', desc, re.I):
                    linguistic.append(re.search(
                        r'\b(developer|engineer|hacker|researcher|analyst)\b', desc, re.I
                    ).group(1).lower())

    # Detect behavioral patterns
    patterns: list[BehavioralPattern] = []
    for persona, persona_platforms in _PLATFORM_SIGNALS.items():
        hits = [p for p in persona_platforms if any(p in s for s in scanners_hit + list(platforms))]
        if hits:
            confidence = min(1.0, len(hits) / len(persona_platforms))
            if confidence >= 0.25:
                patterns.append(BehavioralPattern(
                    pattern_name=persona,
                    confidence=round(confidence, 2),
                    signals=hits,
                    description=_pattern_description(persona, hits),
                ))

    patterns.sort(key=lambda p: p.confidence, reverse=True)
    primary = patterns[0].pattern_name if patterns else "unknown"

    # Activity hours distribution
    hour_counter = Counter(hours_found)
    peak_hours = [h for h, _ in hour_counter.most_common(5)]

    # Risk profile
    has_darkweb = any(p.pattern_name == "darkweb_actor" for p in patterns)
    has_crypto = any(p.pattern_name == "trader_crypto" for p in patterns)
    risk = "high" if has_darkweb else ("medium" if has_crypto else "low")

    return BehavioralFingerprint(
        investigation_id=investigation_id,
        patterns=patterns[:8],
        primary_persona=primary,
        activity_hours=peak_hours,
        platform_footprint=sorted(platforms)[:20],
        linguistic_indicators=list(set(linguistic))[:10],
        risk_profile=risk,
        summary=_build_summary(primary, patterns, risk, len(platforms)),
    )


def _pattern_description(persona: str, signals: list[str]) -> str:
    descriptions = {
        "developer": f"Active developer/engineer — found on {', '.join(signals[:3])}",
        "researcher": f"Academic/research presence — {', '.join(signals[:3])}",
        "trader_crypto": f"Cryptocurrency activity detected — {', '.join(signals[:3])}",
        "social_heavy": f"Heavy social media user — {', '.join(signals[:3])}",
        "security_professional": f"Security/infosec background — {', '.join(signals[:3])}",
        "corporate": f"Corporate/business presence — {', '.join(signals[:3])}",
        "darkweb_actor": f"Dark web activity indicators — {', '.join(signals[:3])}",
    }
    return descriptions.get(persona, f"{persona}: {', '.join(signals[:3])}")


def _build_summary(primary: str, patterns: list[BehavioralPattern], risk: str,
                   platform_count: int) -> str:
    top = ", ".join(p.pattern_name for p in patterns[:3]) if patterns else "no clear pattern"
    return (
        f"Subject exhibits {primary} behavioral profile. "
        f"Footprint spans {platform_count} platforms. "
        f"Top patterns: {top}. Risk level: {risk}."
    )
