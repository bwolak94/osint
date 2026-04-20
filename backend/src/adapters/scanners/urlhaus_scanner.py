"""URLhaus scanner — checks URLs, domains, and IPs against the abuse.ch malware URL database."""

import re
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_URLHAUS_API = "https://urlhaus-api.abuse.ch/v1"


class URLhausScanner(BaseOsintScanner):
    """Queries the URLhaus API (abuse.ch) for malicious URL intelligence.

    No API key required — the service is completely free.

    Supports:
    - URL: direct lookup of a specific URL's malware status.
    - DOMAIN / IP_ADDRESS: host-based lookup returning all known malicious URLs
      hosted on that host.

    Returns malware families, tags, blacklist statuses (SURBL / Google Safe
    Browsing), first/last seen timestamps, and individual malicious URL records.
    Each malicious URL is surfaced as an extracted identifier.
    """

    scanner_name = "urlhaus"
    supported_input_types = frozenset({
        ScanInputType.URL,
        ScanInputType.DOMAIN,
        ScanInputType.IP_ADDRESS,
    })
    cache_ttl = 1800

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20) as client:
            if input_type == ScanInputType.URL:
                return await self._lookup_url(client, input_value)
            # DOMAIN and IP_ADDRESS both use the host endpoint
            return await self._lookup_host(client, input_value)

    async def _lookup_url(self, client: httpx.AsyncClient, url: str) -> dict[str, Any]:
        resp = await client.post(
            f"{_URLHAUS_API}/url/",
            data={"url": url},
        )
        resp.raise_for_status()
        data = resp.json()

        query_status = data.get("query_status", "")
        not_found = query_status in ("no_results", "invalid_url")

        if not_found:
            return {
                "input": url,
                "found": False,
                "query_status": query_status,
                "extracted_identifiers": [],
            }

        blacklists = data.get("blacklists", {})
        identifiers = [f"url:{url}"] if data.get("threat") else []

        return {
            "input": url,
            "found": True,
            "query_status": query_status,
            "id": data.get("id"),
            "url_status": data.get("url_status"),
            "threat": data.get("threat"),
            "tags": data.get("tags") or [],
            "blacklists": {
                "surbl": blacklists.get("surbl", "not listed"),
                "gsb": blacklists.get("gsb", "not listed"),
            },
            "date_added": data.get("date_added"),
            "last_online": data.get("last_online"),
            "reporter": data.get("reporter"),
            "payloads": data.get("payloads") or [],
            "extracted_identifiers": identifiers,
        }

    async def _lookup_host(self, client: httpx.AsyncClient, host: str) -> dict[str, Any]:
        resp = await client.post(
            f"{_URLHAUS_API}/host/",
            data={"host": host},
        )
        resp.raise_for_status()
        data = resp.json()

        query_status = data.get("query_status", "")
        if query_status == "no_results":
            return {
                "input": host,
                "found": False,
                "query_status": query_status,
                "url_count": 0,
                "extracted_identifiers": [],
            }

        urls_data: list[dict[str, Any]] = data.get("urls", []) or []

        malware_families: list[str] = []
        all_tags: list[str] = []
        malicious_urls: list[dict[str, Any]] = []

        for entry in urls_data:
            url_str = entry.get("url", "")
            if url_str:
                malicious_urls.append({
                    "url": url_str,
                    "url_status": entry.get("url_status"),
                    "date_added": entry.get("date_added"),
                    "threat": entry.get("threat"),
                    "tags": entry.get("tags") or [],
                })
            for tag in entry.get("tags") or []:
                if tag not in all_tags:
                    all_tags.append(tag)
            threat = entry.get("threat", "")
            if threat and threat not in malware_families:
                malware_families.append(threat)

        identifiers = [f"url:{entry['url']}" for entry in malicious_urls if entry.get("url")]

        blacklists = data.get("blacklists", {})

        return {
            "input": host,
            "found": True,
            "query_status": query_status,
            "url_count": data.get("url_count", len(urls_data)),
            "urls_with_malware": malicious_urls,
            "malware_families": malware_families,
            "tags": all_tags,
            "first_seen": data.get("first_seen"),
            "last_seen": data.get("last_seen"),
            "blacklists": {
                "surbl": blacklists.get("surbl", "not listed"),
                "gsb": blacklists.get("gsb", "not listed"),
            },
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
