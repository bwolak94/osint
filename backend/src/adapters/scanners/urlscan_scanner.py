"""URLScan.io scanner — search historical website scans for domain/URL intelligence."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.config import get_settings
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_SEARCH_URL = "https://urlscan.io/api/v1/search/"


class URLScanScanner(BaseOsintScanner):
    """Searches urlscan.io for historical scan results related to a domain or URL.

    The search API is free and does not require an API key.
    If URLSCAN_API_KEY is configured in settings, it is sent as an Authorization header
    which unlocks higher rate limits and allows submitting new scans.
    """

    scanner_name = "urlscan"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 7200  # 2 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        settings = get_settings()
        api_key: str = getattr(settings, "urlscan_api_key", "") or ""

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["API-Key"] = api_key

        if input_type == ScanInputType.DOMAIN:
            query = f"domain:{input_value}"
            size = 10
        else:
            # URL input — search by exact page URL
            encoded = quote(input_value, safe="")
            query = f"page.url:{encoded}"
            size = 5

        async with httpx.AsyncClient(timeout=15) as client:
            try:
                resp = await client.get(
                    _SEARCH_URL,
                    params={"q": query, "size": size},
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPStatusError as e:
                log.warning("URLScan HTTP error", input=input_value, status=e.response.status_code)
                return {
                    "input": input_value,
                    "found": False,
                    "error": str(e),
                    "extracted_identifiers": [],
                }
            except Exception as e:
                log.error("URLScan scan failed", input=input_value, error=str(e))
                return {
                    "input": input_value,
                    "found": False,
                    "error": str(e),
                    "extracted_identifiers": [],
                }

        results_raw = data.get("results", [])
        scan_results: list[dict[str, Any]] = []
        seen_ips: set[str] = set()
        seen_urls: set[str] = set()
        identifiers: list[str] = []

        for item in results_raw:
            page = item.get("page", {})
            verdicts = item.get("verdicts", {})
            overall = verdicts.get("overall", {})

            ip = page.get("ip", "")
            url = page.get("url", "")
            screenshot_url = f"https://urlscan.io/screenshots/{item.get('task', {}).get('uuid', '')}.png"

            entry: dict[str, Any] = {
                "url": url,
                "ip": ip,
                "country": page.get("country", ""),
                "server": page.get("server", ""),
                "title": page.get("title", ""),
                "malicious": overall.get("malicious", False),
                "screenshot_url": screenshot_url,
                "certificate": {
                    "subject_name": item.get("page", {}).get("domain", ""),
                    "issuer": "",
                },
                "scan_id": item.get("task", {}).get("uuid", ""),
                "scan_time": item.get("task", {}).get("time", ""),
            }
            scan_results.append(entry)

            if ip and ip not in seen_ips:
                seen_ips.add(ip)
                identifiers.append(f"ip:{ip}")

            if url and url not in seen_urls:
                seen_urls.add(url)
                identifiers.append(f"url:{url}")

        return {
            "input": input_value,
            "found": bool(scan_results),
            "total_results": data.get("total", 0),
            "scan_results": scan_results,
            "unique_ips": list(seen_ips),
            "extracted_identifiers": identifiers,
        }
