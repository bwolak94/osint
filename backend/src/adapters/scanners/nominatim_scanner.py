"""Nominatim scanner — forward and reverse geocoding via OpenStreetMap."""

from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
_IPAPI_URL = "http://ip-api.com/json/{ip}"
_HEADERS = {"User-Agent": "OSINT-Platform/1.0 contact@example.com"}


class NominatimScanner(BaseOsintScanner):
    scanner_name = "nominatim"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.IP_ADDRESS})
    cache_ttl = 86400

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20, headers=_HEADERS) as client:
            if input_type == ScanInputType.IP_ADDRESS:
                return await self._reverse_geocode_ip(client, input_value)
            return await self._forward_geocode(client, input_value)

    async def _forward_geocode(self, client: httpx.AsyncClient, location: str) -> dict[str, Any]:
        params = {
            "q": location,
            "format": "json",
            "addressdetails": "1",
            "limit": "5",
        }
        try:
            resp = await client.get(_SEARCH_URL, params=params)
            if resp.status_code != 200:
                return self._empty_result(location)
            raw = resp.json()
        except Exception as exc:
            log.warning("Nominatim forward geocode failed", location=location, error=str(exc))
            return self._empty_result(location)

        results = self._parse_results(raw)
        best = results[0] if results else {}
        return {
            "input": location,
            "found": bool(results),
            "results": results,
            "best_match": best,
            "country": best.get("country", ""),
            "city": best.get("city", ""),
            "postcode": best.get("postcode", ""),
            "extracted_identifiers": [],
        }

    async def _reverse_geocode_ip(self, client: httpx.AsyncClient, ip: str) -> dict[str, Any]:
        # Step 1: GeoIP lookup
        lat: float | None = None
        lon: float | None = None
        try:
            resp = await client.get(_IPAPI_URL.format(ip=ip))
            if resp.status_code == 200:
                geo = resp.json()
                if geo.get("status") == "success":
                    lat = geo.get("lat")
                    lon = geo.get("lon")
        except Exception as exc:
            log.warning("ip-api.com lookup failed", ip=ip, error=str(exc))

        if lat is None or lon is None:
            return self._empty_result(ip)

        # Step 2: Reverse geocode
        params = {
            "lat": str(lat),
            "lon": str(lon),
            "format": "json",
            "addressdetails": "1",
        }
        try:
            resp = await client.get(_REVERSE_URL, params=params)
            if resp.status_code != 200:
                return self._empty_result(ip)
            raw = resp.json()
        except Exception as exc:
            log.warning("Nominatim reverse geocode failed", lat=lat, lon=lon, error=str(exc))
            return self._empty_result(ip)

        result = self._parse_single(raw)
        return {
            "input": ip,
            "found": bool(result),
            "results": [result] if result else [],
            "best_match": result,
            "country": result.get("country", ""),
            "city": result.get("city", ""),
            "postcode": result.get("postcode", ""),
            "ip_lat": lat,
            "ip_lon": lon,
            "extracted_identifiers": [],
        }

    def _parse_results(self, raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self._parse_single(item) for item in raw]

    def _parse_single(self, item: dict[str, Any]) -> dict[str, Any]:
        address = item.get("address", {})
        return {
            "display_name": item.get("display_name", ""),
            "lat": item.get("lat", ""),
            "lon": item.get("lon", ""),
            "osm_type": item.get("osm_type", ""),
            "importance": item.get("importance", 0.0),
            "country": address.get("country", ""),
            "country_code": address.get("country_code", ""),
            "city": address.get("city") or address.get("town") or address.get("village", ""),
            "postcode": address.get("postcode", ""),
            "state": address.get("state", ""),
            "road": address.get("road", ""),
        }

    def _empty_result(self, input_value: str) -> dict[str, Any]:
        return {
            "input": input_value,
            "found": False,
            "results": [],
            "best_match": {},
            "country": "",
            "city": "",
            "postcode": "",
            "extracted_identifiers": [],
        }
