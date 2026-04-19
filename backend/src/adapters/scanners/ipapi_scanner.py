"""ip-api.com scanner — free IP geolocation, ISP, ASN, and proxy/VPN/hosting detection."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# NOTE: ip-api.com free tier does NOT support HTTPS — HTTP only.
# To use HTTPS you must purchase a Pro plan. The HTTP endpoint is rate-limited
# to 45 requests per minute from a single IP. The `fields` bitmask 66846719
# requests all available fields.
_API_URL = "http://ip-api.com/json/{ip}"
_FIELDS = 66846719


class IPAPIScanner(BaseOsintScanner):
    """Queries ip-api.com for comprehensive IP geolocation and network enrichment.

    Returns continent, country, region, city, ISP, org, ASN, timezone,
    and boolean flags for mobile, proxy/VPN, and hosting/datacenter IPs.

    IMPORTANT: Uses HTTP (not HTTPS) as required by the free tier of ip-api.com.
    No API key required. Rate limit: 45 requests/minute per source IP.
    """

    scanner_name = "ipapi"
    supported_input_types = frozenset({ScanInputType.IP_ADDRESS})
    cache_ttl = 86400  # 24 hours — geolocation data is relatively stable

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        url = _API_URL.format(ip=input_value)

        async with httpx.AsyncClient(timeout=15) as client:
            try:
                resp = await client.get(url, params={"fields": _FIELDS})
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPStatusError as e:
                log.warning("ip-api HTTP error", ip=input_value, status=e.response.status_code)
                return {
                    "input": input_value,
                    "found": False,
                    "error": str(e),
                    "extracted_identifiers": [],
                }
            except Exception as e:
                log.error("ip-api scan failed", ip=input_value, error=str(e))
                return {
                    "input": input_value,
                    "found": False,
                    "error": str(e),
                    "extracted_identifiers": [],
                }

        status = data.get("status", "fail")
        if status != "success":
            return {
                "input": input_value,
                "found": False,
                "error": data.get("message", "ip-api returned failure status"),
                "extracted_identifiers": [],
            }

        # ip-api returns no actionable pivot identifiers — this is pure enrichment
        identifiers: list[str] = []

        return {
            "input": input_value,
            "found": True,
            "query_ip": data.get("query", input_value),
            "continent": data.get("continent", ""),
            "country": data.get("country", ""),
            "country_code": data.get("countryCode", ""),
            "region": data.get("region", ""),
            "region_name": data.get("regionName", ""),
            "city": data.get("city", ""),
            "zip": data.get("zip", ""),
            "lat": data.get("lat"),
            "lon": data.get("lon"),
            "timezone": data.get("timezone", ""),
            "isp": data.get("isp", ""),
            "org": data.get("org", ""),
            "as_number": data.get("as", ""),
            "as_name": data.get("asname", ""),
            "is_mobile": data.get("mobile", False),
            "is_proxy": data.get("proxy", False),
            "is_hosting": data.get("hosting", False),
            "extracted_identifiers": identifiers,
        }
