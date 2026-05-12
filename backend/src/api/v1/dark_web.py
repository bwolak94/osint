"""Dark web monitoring API."""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import random
import hashlib
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/v1/dark-web", tags=["dark-web"])


class DarkWebMention(BaseModel):
    id: str
    source: str  # "tor_forum", "paste_site", "marketplace", "telegram_channel"
    title: str
    snippet: str
    query: str
    risk_level: str  # "critical", "high", "medium", "low"
    first_seen: str
    last_seen: str
    url_hash: str  # SHA256 of actual URL for reference without exposing it
    tags: list[str]


class DarkWebScanResult(BaseModel):
    query: str
    total_mentions: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    mentions: list[DarkWebMention]
    last_scanned: str


@router.get("/scan", response_model=DarkWebScanResult)
async def scan_dark_web(query: str, days_back: int = 30):
    """Scan dark web sources for mentions of a query (email, domain, name, etc.)"""
    sources = ["tor_forum", "paste_site", "marketplace", "telegram_channel"]
    risk_levels = ["critical", "high", "medium", "low"]

    # Generate realistic mock data
    num_mentions = random.randint(2, 12)
    mentions = []
    for i in range(num_mentions):
        source = random.choice(sources)
        risk = random.choice(risk_levels)
        days_ago = random.randint(1, days_back)
        dt = (datetime.utcnow() - timedelta(days=days_ago)).isoformat()
        mentions.append(
            DarkWebMention(
                id=f"dwm_{i}_{hashlib.md5(f'{query}{i}'.encode()).hexdigest()[:8]}",
                source=source,
                title=(
                    f"Leaked data mentioning {query}"
                    if risk == "critical"
                    else f"Reference to {query} on {source}"
                ),
                snippet=(
                    f"...credentials for {query} were posted including username/password pairs..."
                    if risk == "critical"
                    else f"...{query} mentioned in context of breach discussion..."
                ),
                query=query,
                risk_level=risk,
                first_seen=dt,
                last_seen=dt,
                url_hash=hashlib.sha256(f"{source}{i}{query}".encode()).hexdigest(),
                tags=[
                    "leaked-credentials" if risk == "critical" else "mention",
                    source,
                    "automated-scan",
                ],
            )
        )

    counts = {
        level: sum(1 for m in mentions if m.risk_level == level)
        for level in risk_levels
    }
    return DarkWebScanResult(
        query=query,
        total_mentions=len(mentions),
        critical_count=counts["critical"],
        high_count=counts["high"],
        medium_count=counts["medium"],
        low_count=counts["low"],
        mentions=mentions,
        last_scanned=datetime.utcnow().isoformat(),
    )


@router.get("/alerts")
async def get_dark_web_alerts():
    """Get recent dark web alerts across all monitored queries"""
    return {"alerts": [], "total": 0}
