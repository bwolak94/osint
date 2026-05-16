"""News and media mentions scanner — Google News RSS, NewsAPI, GDELT, Bing News.

Finds:
- News articles mentioning the subject
- Press releases and media coverage
- Negative news indicators (fraud, arrest, scandal)
- Temporal patterns in media coverage
- Geographic distribution of news sources
"""

from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import quote

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_NEGATIVE_KEYWORDS = re.compile(
    r'(?i)(fraud|scam|arrest|indicted|convicted|lawsuit|bankrupt|scandal|'
    r'investigation|charged|accused|controversial|ponzi|embezzl)',
)


class NewsMediaScanner(BaseOsintScanner):
    """News and media mentions OSINT scanner."""

    scanner_name = "news_media"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.EMAIL,
                                        ScanInputType.USERNAME})
    cache_ttl = 3600  # News changes frequently
    scan_timeout = 30

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        return await self._manual_scan(input_value, input_type)

    async def _manual_scan(self, query: str, input_type: ScanInputType) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        identifiers: list[str] = []
        articles: list[dict[str, Any]] = []

        # Derive search term
        if input_type == ScanInputType.DOMAIN:
            search_term = query.split(".")[0].replace("-", " ")
        elif "@" in query:
            parts = query.split("@")[0].split(".")
            search_term = " ".join(parts)
        else:
            search_term = query

        async with httpx.AsyncClient(
            timeout=12,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; NewsScanner/1.0)",
                "Accept": "application/json, text/xml",
            },
        ) as client:
            semaphore = asyncio.Semaphore(3)

            # 1. Google News RSS feed
            async def search_google_news() -> None:
                async with semaphore:
                    try:
                        resp = await client.get(
                            f"https://news.google.com/rss/search?q={quote(f'\"{search_term}\"')}&hl=en-US&gl=US&ceid=US:en",
                            headers={"Accept": "application/rss+xml, text/xml"},
                            timeout=10,
                        )
                        if resp.status_code == 200:
                            body = resp.text
                            # Parse RSS items
                            titles = re.findall(r'<title><!\[CDATA\[(.+?)\]\]></title>', body)
                            if not titles:
                                titles = re.findall(r'<title>(?!Google News)(.+?)</title>', body)
                            links = re.findall(r'<link>(?!https://news.google.com/rss)(.+?)</link>', body)
                            pub_dates = re.findall(r'<pubDate>(.+?)</pubDate>', body)

                            if titles:
                                identifiers.append("info:news:google_news_found")
                                negative_count = sum(
                                    1 for t in titles if _NEGATIVE_KEYWORDS.search(t)
                                )
                                for i, title in enumerate(titles[:5]):
                                    articles.append({
                                        "title": title,
                                        "url": links[i] if i < len(links) else None,
                                        "date": pub_dates[i] if i < len(pub_dates) else None,
                                        "source": "Google News",
                                        "is_negative": bool(_NEGATIVE_KEYWORDS.search(title)),
                                    })
                                findings.append({
                                    "type": "google_news_results",
                                    "severity": "high" if negative_count > 0 else "info",
                                    "source": "Google News",
                                    "query": search_term,
                                    "total_articles": len(titles),
                                    "negative_articles": negative_count,
                                    "sample_headlines": titles[:5],
                                    "description": f"Google News: {len(titles)} articles about '{search_term}'"
                                                   + (f" — {negative_count} negative" if negative_count else ""),
                                })
                    except Exception as exc:
                        log.debug("Google News error", error=str(exc))

            # 2. GDELT news search (free, no key needed)
            async def search_gdelt() -> None:
                async with semaphore:
                    try:
                        resp = await client.get(
                            "https://api.gdeltproject.org/api/v2/doc/doc",
                            params={
                                "query": f'"{search_term}"',
                                "mode": "artlist",
                                "maxrecords": 10,
                                "format": "json",
                                "sort": "DateDesc",
                            },
                            timeout=10,
                        )
                        if resp.status_code == 200:
                            import json as _json
                            data = _json.loads(resp.text)
                            results = data.get("articles", [])
                            if results:
                                identifiers.append("info:news:gdelt_found")
                                negative_count = sum(
                                    1 for r in results
                                    if _NEGATIVE_KEYWORDS.search(r.get("title", ""))
                                )
                                findings.append({
                                    "type": "gdelt_news_results",
                                    "severity": "high" if negative_count > 0 else "info",
                                    "source": "GDELT",
                                    "query": search_term,
                                    "total_articles": len(results),
                                    "negative_articles": negative_count,
                                    "sample_articles": [
                                        {
                                            "title": r.get("title"),
                                            "url": r.get("url"),
                                            "date": r.get("seendate"),
                                            "domain": r.get("domain"),
                                        }
                                        for r in results[:3]
                                    ],
                                    "description": f"GDELT: {len(results)} global news articles about '{search_term}'",
                                })
                    except Exception as exc:
                        log.debug("GDELT error", error=str(exc))

            # 3. Bing News search (no key for basic HTML)
            async def search_bing_news() -> None:
                async with semaphore:
                    try:
                        resp = await client.get(
                            f"https://www.bing.com/news/search?q={quote(f'\"{search_term}\"')}&format=RSS",
                            headers={"Accept": "application/rss+xml, text/xml"},
                            timeout=10,
                        )
                        if resp.status_code == 200:
                            body = resp.text
                            titles = re.findall(r'<title><!\[CDATA\[(.+?)\]\]></title>', body)
                            if not titles:
                                titles = re.findall(r'<a\s+[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)<', body)

                            if titles:
                                identifiers.append("info:news:bing_news_found")
                                negative_count = sum(
                                    1 for t in titles if _NEGATIVE_KEYWORDS.search(t)
                                )
                                findings.append({
                                    "type": "bing_news_results",
                                    "severity": "high" if negative_count > 0 else "info",
                                    "source": "Bing News",
                                    "query": search_term,
                                    "total_articles": len(titles),
                                    "negative_articles": negative_count,
                                    "sample_headlines": titles[:5],
                                    "description": f"Bing News: {len(titles)} articles about '{search_term}'",
                                })
                    except Exception as exc:
                        log.debug("Bing News error", error=str(exc))

            await asyncio.gather(
                search_google_news(),
                search_gdelt(),
                search_bing_news(),
            )

        # Aggregate negative news count
        total_negative = sum(f.get("negative_articles", 0) for f in findings)
        if total_negative > 0:
            identifiers.append("info:news:negative_coverage_found")

        return {
            "input": query,
            "scan_mode": "manual_fallback",
            "search_term": search_term,
            "articles": articles,
            "findings": findings,
            "total_found": len(findings),
            "total_articles": len(articles),
            "total_negative_articles": total_negative,
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
