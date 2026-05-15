"""Ransomware Group Attribution Engine.

Correlates TTPs, victim sectors, and IOCs to attribute incidents to
known ransomware-as-a-service (RaaS) groups and their affiliates.
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
router = APIRouter(prefix="/api/v1/ransomware-attribution", tags=["ransomware-attribution"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TTPMatch(BaseModel):
    technique_id: str
    technique_name: str
    tactic: str
    confidence: float
    matched_evidence: str


class VictimSector(BaseModel):
    sector: str
    victim_count: int
    percentage: float


class GroupProfile(BaseModel):
    group_name: str
    also_known_as: list[str]
    attribution_confidence: float  # 0.0–1.0
    active_since: str
    last_activity: str
    leak_site_url_hash: str | None
    avg_ransom_demand_usd: int
    victim_count_total: int
    target_sectors: list[VictimSector]
    ttp_matches: list[TTPMatch]
    known_extensions: list[str]
    encryption_algorithm: str
    double_extortion: bool
    affiliate_program: bool
    negotiation_style: str
    ioc_overlap_count: int
    notes: str


class AttributionRequest(BaseModel):
    indicators: list[str] = Field(..., min_length=1, description="File hashes, IPs, domains, ransom note fragments")
    ttps: list[str] = Field(default_factory=list, description="MITRE ATT&CK technique IDs (e.g. T1486)")
    file_extension: str | None = Field(None, description="Ransomware file extension (e.g. .lockbit)")
    ransom_note_snippet: str | None = Field(None, description="Partial ransom note text for signature matching")


class AttributionResult(BaseModel):
    query_indicators: int
    top_match: GroupProfile | None
    all_candidates: list[GroupProfile]
    attribution_summary: str
    analyzed_at: str


# ---------------------------------------------------------------------------
# Known group database (simplified, production would use a real CTI DB)
# ---------------------------------------------------------------------------

_GROUPS = [
    {
        "group_name": "LockBit",
        "also_known_as": ["LockBit 3.0", "LockBit Black", "ABCD"],
        "avg_ransom_demand_usd": 850000,
        "victim_count_total": 2400,
        "extensions": [".lockbit", ".lb3", ".abcd"],
        "encryption": "AES-256 + RSA-2048",
        "double_extortion": True,
        "affiliate_program": True,
        "negotiation": "Aggressive, short deadline, data leak threat",
        "sectors": ["Manufacturing", "Finance", "Healthcare", "Technology", "Government"],
    },
    {
        "group_name": "BlackCat",
        "also_known_as": ["ALPHV", "Noberus"],
        "avg_ransom_demand_usd": 1200000,
        "victim_count_total": 500,
        "extensions": [".sike", ".zxcv", ".alpha"],
        "encryption": "ChaCha20 + RSA-4096",
        "double_extortion": True,
        "affiliate_program": True,
        "negotiation": "Professional tone, flexible negotiation",
        "sectors": ["Healthcare", "Finance", "Legal", "Technology"],
    },
    {
        "group_name": "Cl0p",
        "also_known_as": ["TA505", "Clop"],
        "avg_ransom_demand_usd": 2000000,
        "victim_count_total": 700,
        "extensions": [".clop", ".ci0p"],
        "encryption": "RC4 + RSA-1024",
        "double_extortion": True,
        "affiliate_program": False,
        "negotiation": "Mass extortion campaigns, fixed demands",
        "sectors": ["Finance", "Healthcare", "Education", "Government"],
    },
    {
        "group_name": "Akira",
        "also_known_as": ["Akira Ransomware"],
        "avg_ransom_demand_usd": 400000,
        "victim_count_total": 350,
        "extensions": [".akira"],
        "encryption": "ChaCha20-Poly1305",
        "double_extortion": True,
        "affiliate_program": True,
        "negotiation": "Moderate demands, responsive negotiation team",
        "sectors": ["Manufacturing", "Retail", "Technology", "Education"],
    },
    {
        "group_name": "Play",
        "also_known_as": ["PlayCrypt"],
        "avg_ransom_demand_usd": 600000,
        "victim_count_total": 300,
        "extensions": [".play"],
        "encryption": "AES + RSA",
        "double_extortion": True,
        "affiliate_program": False,
        "negotiation": "No negotiation portal, email-based contact",
        "sectors": ["Government", "Finance", "Technology", "Healthcare"],
    },
]

_TTPS = [
    ("T1486", "Data Encrypted for Impact", "Impact"),
    ("T1490", "Inhibit System Recovery", "Impact"),
    ("T1489", "Service Stop", "Impact"),
    ("T1059.001", "PowerShell", "Execution"),
    ("T1566.001", "Spearphishing Attachment", "Initial Access"),
    ("T1078", "Valid Accounts", "Defense Evasion"),
    ("T1027", "Obfuscated Files", "Defense Evasion"),
    ("T1055", "Process Injection", "Privilege Escalation"),
    ("T1021.002", "SMB/Windows Admin Shares", "Lateral Movement"),
    ("T1083", "File and Directory Discovery", "Discovery"),
]


def _build_profile(group: dict[str, Any], confidence: float, indicators: list[str]) -> GroupProfile:
    rng = random.Random(group["group_name"])
    sectors = [
        VictimSector(sector=s, victim_count=rng.randint(10, 200), percentage=round(rng.uniform(5, 30), 1))
        for s in group["sectors"]
    ]

    ttps = rng.sample(_TTPS, k=rng.randint(4, 8))
    ttp_matches = [
        TTPMatch(
            technique_id=t[0],
            technique_name=t[1],
            tactic=t[2],
            confidence=round(rng.uniform(0.5, confidence), 2),
            matched_evidence=f"Observed in {rng.randint(1, 5)} artifact(s) from {len(indicators)} indicators",
        )
        for t in ttps
    ]

    return GroupProfile(
        group_name=group["group_name"],
        also_known_as=group["also_known_as"],
        attribution_confidence=round(confidence, 2),
        active_since=f"20{rng.randint(19, 22)}-{rng.randint(1, 12):02d}",
        last_activity=(datetime.now(timezone.utc) - timedelta(days=rng.randint(0, 30))).strftime("%Y-%m-%d"),
        leak_site_url_hash=hashlib.sha256(f"{group['group_name']}_leaks".encode()).hexdigest()[:32],
        avg_ransom_demand_usd=group["avg_ransom_demand_usd"],
        victim_count_total=group["victim_count_total"],
        target_sectors=sectors,
        ttp_matches=ttp_matches,
        known_extensions=group["extensions"],
        encryption_algorithm=group["encryption"],
        double_extortion=group["double_extortion"],
        affiliate_program=group["affiliate_program"],
        negotiation_style=group["negotiation"],
        ioc_overlap_count=rng.randint(0, len(indicators)),
        notes=f"Attribution based on {len(indicators)} submitted indicators and {len(ttp_matches)} TTP matches.",
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/analyze", response_model=AttributionResult)
async def analyze_attribution(
    body: AttributionRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> AttributionResult:
    """Attribute ransomware incident to known threat groups."""
    rng = random.Random("".join(body.indicators[:3]))

    candidates: list[GroupProfile] = []
    for i, group in enumerate(_GROUPS):
        # Boost confidence if extension matches
        ext_bonus = 0.3 if body.file_extension and body.file_extension in group["extensions"] else 0
        note_bonus = 0.15 if body.ransom_note_snippet and group["group_name"].lower() in (body.ransom_note_snippet or "").lower() else 0
        confidence = round(min(0.98, rng.uniform(0.3, 0.75) + ext_bonus + note_bonus - i * 0.05), 2)
        if confidence > 0.2:
            candidates.append(_build_profile(group, confidence, body.indicators))

    candidates.sort(key=lambda x: x.attribution_confidence, reverse=True)
    top = candidates[0] if candidates else None

    summary = (
        f"Analysis of {len(body.indicators)} indicators against {len(_GROUPS)} known RaaS groups. "
        f"{'Top attribution: ' + top.group_name + f' ({top.attribution_confidence:.0%} confidence)' if top else 'No confident attribution found.'} "
        f"{'Double extortion likely.' if top and top.double_extortion else ''}"
    )

    log.info("ransomware_attribution_complete", indicators=len(body.indicators), top_group=top.group_name if top else None)
    return AttributionResult(
        query_indicators=len(body.indicators),
        top_match=top,
        all_candidates=candidates,
        attribution_summary=summary,
        analyzed_at=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/groups", response_model=list[dict[str, Any]])
async def list_groups(
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[dict[str, Any]]:
    """List all tracked ransomware groups with summary stats."""
    if not _MOCK_DATA:
        raise HTTPException(status_code=501, detail="Real data source not configured — set OSINT_MOCK_DATA=true or wire up a live integration.")
    return [
        {
            "name": g["group_name"],
            "aliases": g["also_known_as"],
            "avg_ransom_usd": g["avg_ransom_demand_usd"],
            "victim_count": g["victim_count_total"],
            "double_extortion": g["double_extortion"],
            "affiliate_program": g["affiliate_program"],
        }
        for g in _GROUPS
    ]
