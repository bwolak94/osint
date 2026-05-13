"""Ransomware tracker via ransomware.live open API (no key required).

API docs: https://api.ransomware.live
"""
from __future__ import annotations
from dataclasses import dataclass, field
import httpx

_BASE = "https://api.ransomware.live/v2"


@dataclass
class RansomwareVictim:
    victim: str
    group: str | None = None
    country: str | None = None
    activity: str | None = None
    discovered: str | None = None
    description: str | None = None
    url: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class RansomwareGroup:
    name: str
    description: str | None = None
    locations: list[str] = field(default_factory=list)
    profile_url: str | None = None


@dataclass
class RansomwareReport:
    query: str
    victims: list[RansomwareVictim] = field(default_factory=list)
    group_info: RansomwareGroup | None = None
    total_victims: int = 0
    source: str = "ransomware.live"


async def search_ransomware(query: str) -> RansomwareReport:
    query = query.strip().lower()
    report = RansomwareReport(query=query)

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        # Try to get victims matching the query
        victims = await _search_victims(client, query)
        report.victims = victims
        report.total_victims = len(victims)

        # If query looks like a group name, fetch group profile
        group = await _fetch_group(client, query)
        if group:
            report.group_info = group

    return report


async def _search_victims(client: httpx.AsyncClient, query: str) -> list[RansomwareVictim]:
    try:
        r = await client.get(f"{_BASE}/victims", params={"q": query})
        if r.status_code != 200:
            # Fallback: get recent victims and filter
            r2 = await client.get(f"{_BASE}/recentvictims")
            if r2.status_code != 200:
                return []
            items = r2.json() if isinstance(r2.json(), list) else []
        else:
            items = r.json() if isinstance(r.json(), list) else []

        victims = []
        for item in items[:30]:
            name = (item.get("victim") or item.get("name") or "").lower()
            if query and query not in name and query not in (item.get("group") or "").lower():
                continue
            victims.append(
                RansomwareVictim(
                    victim=item.get("victim") or item.get("name") or "Unknown",
                    group=item.get("group"),
                    country=item.get("country"),
                    activity=item.get("activity"),
                    discovered=item.get("discovered") or item.get("published"),
                    description=item.get("description"),
                    url=item.get("url") or item.get("website"),
                    tags=item.get("tags") or [],
                )
            )
        return victims
    except Exception:
        return []


async def _fetch_group(client: httpx.AsyncClient, query: str) -> RansomwareGroup | None:
    try:
        r = await client.get(f"{_BASE}/group/{query}")
        if r.status_code != 200:
            return None
        data = r.json()
        if not data:
            return None
        if isinstance(data, list):
            data = data[0]
        return RansomwareGroup(
            name=data.get("name") or query,
            description=data.get("description"),
            locations=data.get("locations") or [],
            profile_url=data.get("meta") or data.get("url"),
        )
    except Exception:
        return None
