"""GeoIP scanner — resolves IP addresses to geographic and network information."""

from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()


class GeoIPScanner(BaseOsintScanner):
    """Queries the free ip-api.com service for geolocation and network data."""

    scanner_name = "geoip"
    supported_input_types = frozenset({ScanInputType.IP_ADDRESS})
    cache_ttl = 604800  # 7 days — geo data rarely changes

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"http://ip-api.com/json/{input_value}")
            resp.raise_for_status()
            data = resp.json()

        if data.get("status") == "fail":
            return {
                "ip": input_value,
                "found": False,
                "error": data.get("message", "Lookup failed"),
                "extracted_identifiers": [],
            }

        country = data.get("country", "")
        city = data.get("city", "")
        lat = data.get("lat")
        lon = data.get("lon")
        isp = data.get("isp", "")
        org = data.get("org", "")
        asn = data.get("as", "")  # e.g. "AS13335 Cloudflare, Inc."
        timezone = data.get("timezone", "")
        region = data.get("regionName", "")

        identifiers: list[str] = []
        if isp:
            identifiers.append(f"isp:{isp}")
        if country:
            identifiers.append(f"country:{country}")
        if asn:
            identifiers.append(f"asn:{asn}")

        return {
            "ip": input_value,
            "found": True,
            "country": country,
            "region": region,
            "city": city,
            "lat": lat,
            "lon": lon,
            "isp": isp,
            "org": org,
            "asn": asn,
            "timezone": timezone,
            "extracted_identifiers": identifiers,
        }
