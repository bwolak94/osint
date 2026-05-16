"""People-search aggregator scanner — TruthFinder, BeenVerified, Spokeo, Whitepages probes.

Checks public people-search sites for:
- Profile existence and index entries
- Associated names, addresses, relatives
- Age range and location hints
- Phone/email reverse lookup results
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

_SITES: list[dict[str, str]] = [
    {"name": "TruthFinder", "url": "https://www.truthfinder.com/results/?firstName={q}&lastName="},
    {"name": "BeenVerified", "url": "https://www.beenverified.com/f/search/person?firstName={q}"},
    {"name": "Spokeo", "url": "https://www.spokeo.com/{q}"},
    {"name": "Whitepages", "url": "https://www.whitepages.com/name/{q}"},
    {"name": "PeopleFinder", "url": "https://www.peoplefinder.com/search/?firstName={q}"},
    {"name": "FastPeopleSearch", "url": "https://www.fastpeoplesearch.com/name/{q}"},
    {"name": "Intelius", "url": "https://www.intelius.com/results/?firstName={q}"},
    {"name": "PublicRecordsNow", "url": "https://www.publicrecordsnow.com/name/{q}"},
]

_PROFILE_INDICATORS = re.compile(
    r'(?i)(result[s]?\s+found|profile[s]?\s+found|\d+\s+record|\d+\s+match|'
    r'person\s+found|view\s+full\s+profile|background\s+check)',
)


class PeopleSearchScanner(BaseOsintScanner):
    """Public people-search aggregator scanner."""

    scanner_name = "people_search"
    supported_input_types = frozenset({ScanInputType.USERNAME, ScanInputType.EMAIL,
                                        ScanInputType.PHONE})
    cache_ttl = 86400
    scan_timeout = 45

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        return await self._manual_scan(input_value, input_type)

    async def _manual_scan(self, query: str, input_type: ScanInputType) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        identifiers: list[str] = []
        sites_found: list[str] = []

        search_term = query.split("@")[0].replace(".", " ") if "@" in query else query
        encoded = quote(search_term.replace(" ", "-"))

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            },
        ) as client:
            semaphore = asyncio.Semaphore(4)

            async def check_site(site: dict[str, str]) -> None:
                async with semaphore:
                    try:
                        url = site["url"].format(q=encoded)
                        resp = await client.get(url, timeout=8)
                        if resp.status_code == 200:
                            body = resp.text
                            if _PROFILE_INDICATORS.search(body):
                                # Try to extract result count
                                count_match = re.search(r'(\d[\d,]*)\s+(?:result|record|match|profile)', body, re.I)
                                count = int(count_match.group(1).replace(",", "")) if count_match else None
                                sites_found.append(site["name"])
                                identifiers.append(f"info:people_search:{site['name'].lower().replace(' ', '_')}")
                                findings.append({
                                    "type": "people_search_results",
                                    "severity": "medium",
                                    "source": site["name"],
                                    "query": search_term,
                                    "result_count": count,
                                    "url": url,
                                    "description": f"{site['name']}: {'~' + str(count) + ' results' if count else 'Profile results'} for '{search_term}'",
                                })
                    except Exception as exc:
                        log.debug("People search site error", site=site["name"], error=str(exc))

            await asyncio.gather(*[check_site(s) for s in _SITES])

        if sites_found:
            findings.insert(0, {
                "type": "people_search_summary",
                "severity": "medium",
                "sites_found": sites_found,
                "query": search_term,
                "description": f"People-search records found on {len(sites_found)} site(s): {', '.join(sites_found)}",
            })

        return {
            "input": query,
            "scan_mode": "manual_fallback",
            "search_term": search_term,
            "sites_checked": len(_SITES),
            "sites_with_results": sites_found,
            "findings": findings,
            "total_found": len(findings),
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
