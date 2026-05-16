"""Dark web forum monitor scanner — searches for mentions on public dark-web indexes.

Uses publicly accessible clearnet dark-web indexes and search aggregators:
- Ahmia.fi (Tor search engine, clearnet proxy)
- DarkSearch.io (dark web search API)
- DeepSearch public indexes
- Intelx.io public results
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_RESULT_RE = re.compile(r'(?i)(result|onion|\.onion|hidden\s+service|tor\s+network)')


class DarkWebForumScanner(BaseOsintScanner):
    """Dark web mention monitor using clearnet aggregator indexes."""

    scanner_name = "darkweb_forum"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.EMAIL,
                                        ScanInputType.USERNAME})
    cache_ttl = 7200
    scan_timeout = 30

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        return await self._manual_scan(input_value, input_type)

    async def _manual_scan(self, query: str, input_type: ScanInputType) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        identifiers: list[str] = []
        encoded = quote(query)

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/json",
            },
        ) as client:
            # 1. Ahmia.fi — clearnet Tor search engine
            try:
                resp = await client.get(
                    f"https://ahmia.fi/search/?q={encoded}",
                    timeout=8,
                )
                if resp.status_code == 200:
                    body = resp.text
                    # Count .onion results
                    onion_links = re.findall(r'[a-z2-7]{16,56}\.onion', body, re.I)
                    unique_onions = list(set(onion_links))
                    count_match = re.search(r'(\d+)\s+(?:result|site)', body, re.I)
                    count = int(count_match.group(1)) if count_match else len(unique_onions)
                    if unique_onions or count:
                        identifiers.append("high:darkweb:ahmia_mention")
                        findings.append({
                            "type": "darkweb_mention",
                            "severity": "high",
                            "source": "Ahmia.fi",
                            "query": query,
                            "result_count": count,
                            "onion_services_found": unique_onions[:5],
                            "url": f"https://ahmia.fi/search/?q={encoded}",
                            "description": f"Ahmia: {count} dark web results for '{query}'",
                        })
            except Exception as exc:
                log.debug("Ahmia search error", error=str(exc))

            # 2. DarkSearch.io API (free tier)
            try:
                resp = await client.get(
                    f"https://darksearch.io/api/search?query={encoded}&page=1",
                    timeout=8,
                )
                if resp.status_code == 200:
                    import json as _json
                    data = _json.loads(resp.text)
                    results = data.get("data", [])
                    total = data.get("total", 0)
                    if results or total:
                        identifiers.append("high:darkweb:darksearch_mention")
                        findings.append({
                            "type": "darkweb_mention",
                            "severity": "high",
                            "source": "DarkSearch.io",
                            "query": query,
                            "result_count": total,
                            "sample_titles": [r.get("title", "") for r in results[:3]],
                            "sample_links": [r.get("link", "") for r in results[:3]],
                            "description": f"DarkSearch: {total} dark web pages mention '{query}'",
                        })
            except Exception as exc:
                log.debug("DarkSearch error", error=str(exc))

            # 3. IntelX.io public search hint
            try:
                resp = await client.post(
                    "https://2.intelx.io/intelligent/search",
                    json={"term": query, "buckets": [], "lookuplevel": 0, "maxresults": 5,
                          "timeout": 0, "datefrom": "", "dateto": "", "sort": 4,
                          "media": 0, "terminate": []},
                    headers={"x-key": ""},
                    timeout=8,
                )
                if resp.status_code == 200:
                    import json as _json
                    data = _json.loads(resp.text)
                    search_id = data.get("id", "")
                    if search_id:
                        identifiers.append("medium:darkweb:intelx_indexed")
                        findings.append({
                            "type": "darkweb_indexed",
                            "severity": "medium",
                            "source": "IntelX.io",
                            "query": query,
                            "search_id": search_id,
                            "description": f"IntelX: query '{query}' indexed — search ID {search_id}",
                        })
            except Exception as exc:
                log.debug("IntelX search error", error=str(exc))

        if findings:
            findings.insert(0, {
                "type": "darkweb_summary",
                "severity": "high",
                "sources_found": [f["source"] for f in findings],
                "query": query,
                "description": f"Dark web mentions found across {len(findings)} source(s) for '{query}'",
            })

        return {
            "input": query,
            "scan_mode": "manual_fallback",
            "query": query,
            "findings": findings,
            "total_found": len(findings),
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
