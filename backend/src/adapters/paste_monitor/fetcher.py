"""Paste monitor — search paste sites for mentions of email/domain/username.

Uses publicly accessible search interfaces that don't require authentication.
Primary source: IntelligenceX (limited free tier) + psbdmp.ws (Pastebin dump search).
"""
from __future__ import annotations
import hashlib
from dataclasses import dataclass, field
import httpx

_PSBDMP = "https://psbdmp.ws/api/v3/search"


@dataclass
class PasteMention:
    id: str
    title: str | None = None
    snippet: str | None = None
    url: str | None = None
    date: str | None = None
    source: str = "pastebin"
    tags: list[str] = field(default_factory=list)


@dataclass
class PasteMonitorResult:
    query: str
    total: int = 0
    mentions: list[PasteMention] = field(default_factory=list)
    source: str = "paste_monitor"


async def search_pastes(query: str) -> PasteMonitorResult:
    query = query.strip()
    result = PasteMonitorResult(query=query)

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        mentions = await _search_psbdmp(client, query)
        result.mentions = mentions
        result.total = len(mentions)

    return result


async def _search_psbdmp(client: httpx.AsyncClient, query: str) -> list[PasteMention]:
    try:
        r = await client.get(_PSBDMP, params={"q": query})
        if r.status_code != 200:
            return []
        data = r.json()
        items = data if isinstance(data, list) else data.get("data", [])
        mentions = []
        for item in items[:50]:
            pid = item.get("id", "")
            text = item.get("text", "") or ""
            snippet = text[:300].replace("\n", " ").strip()
            tags: list[str] = []
            if "@" in query and query.lower() in text.lower():
                tags.append("email-match")
            if "password" in text.lower():
                tags.append("credentials")
            if "api_key" in text.lower() or "apikey" in text.lower():
                tags.append("api-key")
            mentions.append(
                PasteMention(
                    id=pid or hashlib.sha256(text[:50].encode()).hexdigest()[:12],
                    title=item.get("tags") or f"Paste {pid}",
                    snippet=snippet or None,
                    url=f"https://pastebin.com/{pid}" if pid else None,
                    date=item.get("time"),
                    source="pastebin",
                    tags=tags,
                )
            )
        return mentions
    except Exception:
        return []
