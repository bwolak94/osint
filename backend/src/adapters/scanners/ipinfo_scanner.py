"""IPInfo.io scanner — IP geolocation, hostname, ASN, and abuse contact enrichment."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.config import get_settings
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_BASE_URL = "https://ipinfo.io/{ip}/json"


class IPInfoScanner(BaseOsintScanner):
    """Queries ipinfo.io for IP geolocation, hostname, org/ASN, and abuse contact data.

    Free tier: ~50k requests/month with an API key; limited without.
    If config.ipinfo_api_key is set it is sent as a Bearer Authorization header.
    With a paid Privacy Detection add-on, VPN/proxy/Tor fields are also populated.
    """

    scanner_name = "ipinfo"
    supported_input_types = frozenset({ScanInputType.IP_ADDRESS})
    cache_ttl = 86400  # 24 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        settings = get_settings()
        api_key: str = getattr(settings, "ipinfo_api_key", "") or ""

        headers: dict[str, str] = {"Accept": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        url = _BASE_URL.format(ip=input_value)

        async with httpx.AsyncClient(timeout=15) as client:
            try:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPStatusError as e:
                log.warning("IPInfo HTTP error", ip=input_value, status=e.response.status_code)
                return {
                    "input": input_value,
                    "found": False,
                    "error": str(e),
                    "extracted_identifiers": [],
                }
            except Exception as e:
                log.error("IPInfo scan failed", ip=input_value, error=str(e))
                return {
                    "input": input_value,
                    "found": False,
                    "error": str(e),
                    "extracted_identifiers": [],
                }

        if "bogon" in data:
            # Reserved/private IP space — ipinfo marks these as bogon
            return {
                "input": input_value,
                "found": False,
                "bogon": True,
                "extracted_identifiers": [],
            }

        hostname = data.get("hostname", "")
        identifiers: list[str] = []
        if hostname:
            identifiers.append(f"domain:{hostname}")

        # Parse lat/lon from "loc" field ("37.3861,-122.0839")
        lat: float | None = None
        lon: float | None = None
        loc = data.get("loc", "")
        if loc and "," in loc:
            try:
                lat_str, lon_str = loc.split(",", 1)
                lat = float(lat_str)
                lon = float(lon_str)
            except ValueError:
                pass

        # Privacy Detection fields (available with paid add-on)
        privacy = data.get("privacy", {})

        return {
            "input": input_value,
            "found": True,
            "ip": data.get("ip", input_value),
            "hostname": hostname,
            "city": data.get("city", ""),
            "region": data.get("region", ""),
            "country": data.get("country", ""),
            "lat": lat,
            "lon": lon,
            "org": data.get("org", ""),  # e.g. "AS15169 Google LLC"
            "postal": data.get("postal", ""),
            "timezone": data.get("timezone", ""),
            "abuse_contact": data.get("abuse", {}).get("email", ""),
            "is_vpn": privacy.get("vpn", False),
            "is_proxy": privacy.get("proxy", False),
            "is_tor": privacy.get("tor", False),
            "is_hosting": privacy.get("hosting", False),
            "extracted_identifiers": identifiers,
        }
