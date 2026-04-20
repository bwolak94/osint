"""Public WiFi Mapper Scanner — Wigle.net wireless network aggregation near coordinates.

OPSEC intelligence value:
  - WiFi network SSIDs near a target location can reveal: building names, company identifiers,
    personal names (home routers), and infrastructure owner clues.
  - First-seen / last-seen timestamps from Wigle.net establish historical presence of a network,
    confirming when a target moved into or out of an area.
  - BSSID (MAC address) combined with Wigle historical data can geolocate a specific device
    even when it is no longer broadcasting.
  - Encryption type reveals security posture: open networks indicate public venues or poor OPSEC;
    WPA2-Enterprise suggests corporate/institutional environment.
  - High density of similarly-named SSIDs (e.g., "Hotel_Guest_*") confirms venue type.

Input entities:  COORDINATES — "lat,lon" decimal string
Output entities:
  - networks_found      — list of WiFi network metadata within ±0.01 degree (~1 km)
  - total_count         — total matching networks from Wigle
  - encryption_stats    — breakdown by encryption type
  - search_urls         — Wigle.net map URL for manual investigation
  - educational_note    — WiFi OSINT and Wigle.net methodology
"""

from __future__ import annotations

import base64
import os
from collections import Counter
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_WIGLE_SEARCH_URL = "https://api.wigle.net/api/v2/network/search"
_HEADERS = {"User-Agent": "OSINT-Platform/1.0 contact@example.com"}
_COORD_DELTA = 0.01  # ±0.01 degrees ≈ ±1.1 km

_EDUCATIONAL_NOTE = (
    "WiFi OSINT with Wigle.net: "
    "Wigle.net is the world's largest crowdsourced wireless network database, containing "
    "hundreds of millions of BSSIDs with associated GPS coordinates and timestamps. "
    "OSINT applications: "
    "1) Geolocation of a device — if BSSID is known (from email headers, malware artefacts, "
    "   IoT firmware), Wigle can reveal its physical address. "
    "2) Venue identification — SSID names often directly identify businesses or residences. "
    "3) Historical tracking — first/last-seen timestamps reveal when equipment was deployed. "
    "4) Infrastructure mapping — corporate campus SSIDs reveal perimeter of wireless coverage. "
    "5) Operational security assessment — open networks adjacent to a target facility "
    "   represent potential pivot points or data exfiltration channels. "
    "Note: Wigle.net requires free account registration for API access (WIGLE_API_NAME + "
    "WIGLE_API_TOKEN env vars as Basic Auth credentials)."
)


def _build_wigle_map_url(lat: float, lon: float) -> str:
    return f"https://wigle.net/mapsearch?maplat={lat}&maplon={lon}&mapzoom=15"


def _encryption_label(capabilities: str) -> str:
    caps = capabilities.upper()
    if "WPA3" in caps:
        return "WPA3"
    if "WPA2" in caps and "ENTERPRISE" in caps:
        return "WPA2-Enterprise"
    if "WPA2" in caps:
        return "WPA2"
    if "WPA" in caps:
        return "WPA"
    if "WEP" in caps:
        return "WEP (weak)"
    if "ESS" in caps and "WPA" not in caps and "WEP" not in caps:
        return "Open"
    return "Unknown"


class PublicWifiMapperScanner(BaseOsintScanner):
    """Map public WiFi networks near given coordinates using Wigle.net API.

    Input:  ScanInputType.COORDINATES — "lat,lon" string.
    Output: networks_found list, total_count, encryption_stats, search_urls.

    Required environment variables (for API access):
      - WIGLE_API_NAME  — Wigle.net account name (used as Basic Auth username)
      - WIGLE_API_TOKEN — Wigle.net API token (used as Basic Auth password)
    """

    scanner_name = "public_wifi_mapper"
    supported_input_types = frozenset({ScanInputType.COORDINATES})
    cache_ttl = 3600

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        lat, lon = self._parse_coordinates(input_value)
        if lat is None or lon is None:
            return self._error_result(input_value, "Invalid coordinate format. Expected 'lat,lon'.")

        wigle_name = os.getenv("WIGLE_API_NAME")
        wigle_token = os.getenv("WIGLE_API_TOKEN")

        search_urls = {
            "wigle_map": _build_wigle_map_url(lat, lon),
        }

        if not wigle_name or not wigle_token:
            log.info("Wigle credentials not configured — returning manual URL only", lat=lat, lon=lon)
            return {
                "input": input_value,
                "found": False,
                "lat": lat,
                "lon": lon,
                "networks_found": [],
                "total_count": 0,
                "encryption_stats": {},
                "search_urls": search_urls,
                "note": "Set WIGLE_API_NAME and WIGLE_API_TOKEN environment variables for API access.",
                "educational_note": _EDUCATIONAL_NOTE,
                "extracted_identifiers": [f"coordinates:{lat},{lon}"],
            }

        networks, total_count = await self._query_wigle(lat, lon, wigle_name, wigle_token)

        encryption_counter: Counter[str] = Counter()
        for net in networks:
            encryption_counter[net.get("encryption", "Unknown")] += 1
        encryption_stats = dict(encryption_counter.most_common())

        return {
            "input": input_value,
            "found": total_count > 0,
            "lat": lat,
            "lon": lon,
            "networks_found": networks,
            "total_count": total_count,
            "encryption_stats": encryption_stats,
            "search_urls": search_urls,
            "educational_note": _EDUCATIONAL_NOTE,
            "extracted_identifiers": [f"coordinates:{lat},{lon}"],
        }

    # ------------------------------------------------------------------
    # Coordinate parsing
    # ------------------------------------------------------------------

    def _parse_coordinates(self, value: str) -> tuple[float | None, float | None]:
        try:
            parts = value.strip().split(",")
            if len(parts) < 2:
                return None, None
            lat = float(parts[0].strip())
            lon = float(parts[1].strip())
            if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                return None, None
            return lat, lon
        except ValueError:
            return None, None

    # ------------------------------------------------------------------
    # Wigle.net API
    # ------------------------------------------------------------------

    async def _query_wigle(
        self, lat: float, lon: float, api_name: str, api_token: str
    ) -> tuple[list[dict[str, Any]], int]:
        """Query Wigle.net network/search endpoint with Basic Auth."""
        credentials = base64.b64encode(f"{api_name}:{api_token}".encode()).decode()
        headers = {
            **_HEADERS,
            "Authorization": f"Basic {credentials}",
            "Accept": "application/json",
        }
        params = {
            "latrange1": str(lat - _COORD_DELTA),
            "latrange2": str(lat + _COORD_DELTA),
            "longrange1": str(lon - _COORD_DELTA),
            "longrange2": str(lon + _COORD_DELTA),
            "freenet": "false",
            "paynet": "false",
            "resultsPerPage": "100",
            "first": "0",
        }
        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                resp = await client.get(_WIGLE_SEARCH_URL, params=params, headers=headers)
                if resp.status_code == 401:
                    log.warning("Wigle auth failed — check WIGLE_API_NAME and WIGLE_API_TOKEN")
                    return [], 0
                if resp.status_code == 429:
                    log.warning("Wigle rate limited")
                    return [], 0
                if resp.status_code != 200:
                    log.warning("Wigle API error", status=resp.status_code)
                    return [], 0

                data = resp.json()
                if not data.get("success"):
                    log.warning("Wigle API returned success=false", message=data.get("message"))
                    return [], 0

                total_count: int = data.get("totalResults", 0)
                raw_results: list[dict[str, Any]] = data.get("results", [])

                networks: list[dict[str, Any]] = []
                for r in raw_results:
                    capabilities = r.get("capabilities", "")
                    networks.append({
                        "ssid": r.get("ssid", ""),
                        "bssid": r.get("netid", ""),
                        "encryption": _encryption_label(capabilities),
                        "capabilities_raw": capabilities,
                        "first_seen": r.get("firsttime"),
                        "last_seen": r.get("lasttime"),
                        "lat": r.get("trilat"),
                        "lon": r.get("trilong"),
                        "channel": r.get("channel"),
                        "frequency": r.get("frequency"),
                        "type": r.get("type"),
                        "wigle_url": f"https://wigle.net/map?maplat={r.get('trilat')}&maplon={r.get('trilong')}&mapzoom=18",
                    })

                return networks, total_count

        except Exception as exc:
            log.error("Wigle query failed", lat=lat, lon=lon, error=str(exc))
            return [], 0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _error_result(self, input_value: str, error: str) -> dict[str, Any]:
        return {
            "input": input_value,
            "found": False,
            "error": error,
            "networks_found": [],
            "total_count": 0,
            "encryption_stats": {},
            "search_urls": {},
            "educational_note": _EDUCATIONAL_NOTE,
            "extracted_identifiers": [],
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        identifiers = raw_data.get("extracted_identifiers", [])
        for net in raw_data.get("networks_found", []):
            ssid = net.get("ssid", "").strip()
            if ssid and len(ssid) > 2:
                identifiers.append(f"ssid:{ssid}")
        return list(dict.fromkeys(identifiers))
