"""GDELT 2.0 scanner — global news event and article search."""

from typing import Any
from urllib.parse import quote

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"


class GDELTScanner(BaseOsintScanner):
    scanner_name = "gdelt"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.USERNAME})
    cache_ttl = 3600

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        if input_type == ScanInputType.DOMAIN:
            query = input_value.lower().removeprefix("www.").split(".")[0]
        else:
            query = input_value

        async with httpx.AsyncClient(timeout=30) as client:
            articles, top_themes, top_locations = await self._fetch_articles(client, query)
            volume_timeline = await self._fetch_volume_timeline(client, query)

        identifiers: list[str] = []
        for article in articles[:5]:
            url = article.get("url", "")
            if url:
                identifiers.append(f"url:{url}")

        return {
            "input": input_value,
            "query": query,
            "found": bool(articles),
            "articles": articles,
            "volume_timeline": volume_timeline,
            "top_themes": top_themes,
            "top_locations": top_locations,
            "total_articles": len(articles),
            "extracted_identifiers": identifiers,
        }

    async def _fetch_articles(
        self, client: httpx.AsyncClient, query: str
    ) -> tuple[list[dict[str, Any]], list[str], list[str]]:
        params = {
            "query": query,
            "mode": "artlist",
            "maxrecords": "25",
            "format": "json",
        }
        try:
            resp = await client.get(_DOC_API, params=params)
            if resp.status_code != 200:
                return [], [], []
            data = resp.json()
            raw_articles = data.get("articles", [])
            articles: list[dict[str, Any]] = [
                {
                    "url": a.get("url", ""),
                    "title": a.get("title", ""),
                    "seendate": a.get("seendate", ""),
                    "domain": a.get("domain", ""),
                    "language": a.get("language", ""),
                    "sourcecountry": a.get("sourcecountry", ""),
                }
                for a in raw_articles
            ]
            # Derive top themes and locations from tone/socialimage data if present
            top_themes: list[str] = list({a.get("socialimage", "") for a in raw_articles if a.get("socialimage")})[:5]
            top_locations: list[str] = list({a.get("sourcecountry", "") for a in raw_articles if a.get("sourcecountry")})[:10]
            return articles, top_themes, top_locations
        except Exception as exc:
            log.warning("GDELT article fetch failed", query=query, error=str(exc))
            return [], [], []

    async def _fetch_volume_timeline(
        self, client: httpx.AsyncClient, query: str
    ) -> list[dict[str, Any]]:
        params = {
            "query": query,
            "mode": "timelinevolratio",
            "format": "json",
        }
        try:
            resp = await client.get(_DOC_API, params=params)
            if resp.status_code != 200:
                return []
            data = resp.json()
            timeline = data.get("timeline", [])
            if not timeline:
                return []
            # First series in timeline
            series = timeline[0].get("data", []) if timeline else []
            return [{"date": point.get("date", ""), "value": point.get("value", 0)} for point in series[:30]]
        except Exception as exc:
            log.warning("GDELT timeline fetch failed", query=query, error=str(exc))
            return []
