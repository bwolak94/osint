"""Wi-Fi network OSINT scanner — WiGLE.net API.

Finds:
- Wi-Fi networks associated with an address/location/SSID query
- SSID geolocation (lat/lon bounding box from WiGLE database)
- Network encryption type (WPA2, WEP, open)
- First/last seen timestamps
- BSSID (MAC address) of access points
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

_WIGLE_API = "https://api.wigle.net/api/v2"


class WiGLEScanner(BaseOsintScanner):
    """Wi-Fi SSID / BSSID geolocation scanner via WiGLE.net."""

    scanner_name = "wigle"
    supported_input_types = frozenset({ScanInputType.USERNAME, ScanInputType.DOMAIN,
                                        ScanInputType.EMAIL})
    cache_ttl = 86400
    scan_timeout = 20

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        return await self._manual_scan(input_value, input_type)

    async def _manual_scan(self, query: str, input_type: ScanInputType) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        identifiers: list[str] = []
        networks: list[dict[str, Any]] = []

        # Derive SSID search term from input
        if input_type == ScanInputType.DOMAIN:
            ssid_query = query.split(".")[0].replace("-", "").replace("_", "")
        elif "@" in query:
            ssid_query = query.split("@")[1].split(".")[0]
        else:
            ssid_query = query

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; WiGLEScanner/1.0)",
                "Accept": "application/json",
            },
        ) as client:
            # 1. WiGLE SSID search (no auth for basic queries via public search)
            try:
                resp = await client.get(
                    f"{_WIGLE_API}/network/search",
                    params={
                        "ssid": ssid_query,
                        "resultsPerPage": 10,
                        "onlymine": "false",
                    },
                    headers={"Authorization": "Basic "},
                )
                if resp.status_code in (200, 401):
                    import json as _json
                    try:
                        data = _json.loads(resp.text)
                        total = data.get("totalResults", 0)
                        results = data.get("results", [])
                        if total and total > 0:
                            identifiers.append("info:wigle:ssid_found")
                            for net in results[:5]:
                                networks.append({
                                    "ssid": net.get("ssid"),
                                    "bssid": net.get("netid"),
                                    "encryption": net.get("encryption"),
                                    "lat": net.get("trilat"),
                                    "lon": net.get("trilong"),
                                    "city": net.get("city"),
                                    "country": net.get("country"),
                                    "first_seen": net.get("firsttime"),
                                    "last_seen": net.get("lasttime"),
                                })
                            findings.append({
                                "type": "wifi_networks_found",
                                "severity": "info",
                                "source": "WiGLE.net",
                                "query_ssid": ssid_query,
                                "total_networks": total,
                                "sample_networks": networks[:5],
                                "description": f"WiGLE: {total} Wi-Fi networks matching SSID '{ssid_query}'",
                            })
                    except Exception:
                        pass
            except Exception as exc:
                log.debug("WiGLE search error", error=str(exc))

            # 2. Check WiGLE stats API (public, no auth needed)
            try:
                resp = await client.get(f"{_WIGLE_API}/stats/site")
                if resp.status_code == 200:
                    import json as _json
                    data = _json.loads(resp.text)
                    total_nets = data.get("statistics", {}).get("netwireless", 0)
                    if total_nets:
                        findings.append({
                            "type": "wigle_database_info",
                            "severity": "info",
                            "source": "WiGLE.net",
                            "total_wifi_networks_in_db": total_nets,
                            "description": f"WiGLE database contains {total_nets:,} Wi-Fi networks globally",
                        })
            except Exception as exc:
                log.debug("WiGLE stats error", error=str(exc))

        return {
            "input": query,
            "scan_mode": "manual_fallback",
            "ssid_query": ssid_query,
            "networks": networks,
            "findings": findings,
            "total_found": len(findings),
            "total_networks": len(networks),
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
