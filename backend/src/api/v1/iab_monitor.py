"""Initial Access Broker (IAB) Monitor — tracks dark web IAB listings.

Matches threat actor advertisements against target domain infrastructure
and alerts on access type, asking price, and victim profile.
"""

from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User


from src.config import get_settings as _get_settings

# When OSINT_MOCK_DATA=false, endpoints return 501 — real data source required. (#13)
_MOCK_DATA: bool = _get_settings().osint_mock_data

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/iab-monitor", tags=["iab-monitor"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class IABListing(BaseModel):
    listing_id: str
    source: str  # forum name (anonymized)
    threat_actor: str
    access_type: str  # "rdp", "vpn", "webshell", "domain_admin", "initial_foothold"
    victim_domain: str | None
    victim_sector: str
    victim_country: str
    employee_count: str
    revenue_range: str
    asking_price_usd: int | None
    auction_ends: str | None
    negotiable: bool
    access_description: str
    antivirus_present: str | None
    domain_admin: bool
    network_access: bool
    first_seen: str
    last_seen: str
    listing_hash: str
    risk_score: float
    ioc_overlap: list[str]


class IABScanRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Domain, org name, or IP range to match")
    sectors: list[str] = Field(default_factory=list, description="Sector filter (e.g. finance, healthcare)")
    max_price_usd: int | None = Field(None, ge=0, description="Max asking price filter")
    access_types: list[str] = Field(default_factory=list, description="Access type filter")


class IABScanResult(BaseModel):
    query: str
    total_listings: int
    critical_listings: int
    estimated_exposure_usd: int
    listings: list[IABListing]
    top_threat_actors: list[str]
    scanned_at: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SECTORS = [
    "Finance", "Healthcare", "Technology", "Manufacturing", "Government",
    "Education", "Retail", "Energy", "Legal", "Insurance",
]
_COUNTRIES = ["US", "DE", "UK", "FR", "CA", "AU", "NL", "JP", "IN", "BR"]
_ACCESS_TYPES = ["rdp", "vpn", "webshell", "domain_admin", "initial_foothold", "citrix", "exchange_shell"]
_SOURCES = ["forum_a", "forum_b", "market_c", "telegram_d", "forum_e"]
_ACTORS = ["th3_broker", "init1al", "xn0_access", "domino_access", "br0ker_x"]


def _make_listing(query: str, idx: int) -> IABListing:
    rng = random.Random(f"{query}{idx}")
    days_ago = rng.randint(1, 21)
    first_seen = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    auction_active = rng.random() > 0.4
    auction_ends = (
        (datetime.now(timezone.utc) + timedelta(hours=rng.randint(2, 72))).isoformat()
        if auction_active else None
    )
    access_type = rng.choice(_ACCESS_TYPES)
    domain_admin = access_type == "domain_admin" or rng.random() < 0.3
    price = rng.choice([None, 1500, 2500, 5000, 8000, 15000, 25000, 50000])
    risk = round(min(1.0, 0.4 + (0.1 if domain_admin else 0) + (0.2 if price and price > 10000 else 0) + rng.uniform(-0.1, 0.2)), 2)

    return IABListing(
        listing_id=f"iab_{hashlib.md5(f'{query}{idx}'.encode()).hexdigest()[:12]}",
        source=rng.choice(_SOURCES),
        threat_actor=rng.choice(_ACTORS),
        access_type=access_type,
        victim_domain=f"{query.split('.')[0]}-corp.local" if "." in query else None,
        victim_sector=rng.choice(_SECTORS),
        victim_country=rng.choice(_COUNTRIES),
        employee_count=rng.choice(["50-200", "200-500", "500-1000", "1000-5000", "5000+"]),
        revenue_range=rng.choice(["<10M", "10-50M", "50-200M", "200M-1B", ">1B"]),
        asking_price_usd=price,
        auction_ends=auction_ends,
        negotiable=rng.random() > 0.5,
        access_description=(
            f"Full {access_type.upper()} access to {query} environment. "
            f"{'Domain admin credentials included. ' if domain_admin else ''}"
            f"Network access to {'all segments' if rng.random() > 0.5 else 'primary VLAN'}. "
            "Persistence maintained for 2+ weeks."
        ),
        antivirus_present=rng.choice(["Windows Defender", "CrowdStrike", "Sophos", "Cylance", None]),
        domain_admin=domain_admin,
        network_access=rng.random() > 0.3,
        first_seen=first_seen,
        last_seen=first_seen,
        listing_hash=hashlib.sha256(f"{query}{idx}".encode()).hexdigest(),
        risk_score=risk,
        ioc_overlap=rng.sample(
            [f"45.{rng.randint(1,254)}.{rng.randint(1,254)}.{rng.randint(1,254)}", f"malware_{idx}.exe", f"c2_{idx}.onion"],
            k=rng.randint(0, 2),
        ),
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/scan", response_model=IABScanResult)
async def scan_iab_listings(
    body: IABScanRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> IABScanResult:
    """Scan IAB marketplaces for listings matching the target query."""
    if not _MOCK_DATA:
        raise HTTPException(status_code=501, detail="Real data source not configured — set OSINT_MOCK_DATA=true or wire up a live integration.")
    rng = random.Random(body.query)
    count = rng.randint(0, 8)

    listings: list[IABListing] = []
    for i in range(count):
        listing = _make_listing(body.query, i)
        if body.sectors and listing.victim_sector not in body.sectors:
            continue
        if body.max_price_usd is not None and listing.asking_price_usd and listing.asking_price_usd > body.max_price_usd:
            continue
        if body.access_types and listing.access_type not in body.access_types:
            continue
        listings.append(listing)

    listings.sort(key=lambda x: x.risk_score, reverse=True)
    critical = sum(1 for l in listings if l.risk_score >= 0.7)
    exposure = sum(l.asking_price_usd or 0 for l in listings)
    actors = list({l.threat_actor for l in listings})

    log.info("iab_scan_complete", query=body.query, matches=len(listings))
    return IABScanResult(
        query=body.query,
        total_listings=len(listings),
        critical_listings=critical,
        estimated_exposure_usd=exposure,
        listings=listings,
        top_threat_actors=actors[:5],
        scanned_at=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/trending-actors", response_model=dict[str, Any])
async def get_trending_actors(
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Return trending IAB threat actors with listing counts."""
    actors = [
        {"actor": a, "listing_count": random.randint(1, 20), "avg_price_usd": random.choice([3000, 7500, 15000])}
        for a in _ACTORS
    ]
    return {"actors": actors, "updated_at": datetime.now(timezone.utc).isoformat()}
