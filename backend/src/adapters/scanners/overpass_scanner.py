"""Overpass API scanner — OpenStreetMap geospatial feature queries."""

from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_NOMINATIM_HEADERS = {"User-Agent": "OSINT-Platform/1.0 contact@example.com"}
_RADIUS_M = 500


def _build_overpass_query(lat: float, lon: float, radius: int = _RADIUS_M) -> str:
    return f"""
[out:json][timeout:25];
(
  node["man_made"="surveillance"](around:{radius},{lat},{lon});
  way["landuse"="military"](around:{radius},{lat},{lon});
  relation["landuse"="military"](around:{radius},{lat},{lon});
  node["building"="government"](around:{radius},{lat},{lon});
  way["building"="government"](around:{radius},{lat},{lon});
  node["amenity"="bank"](around:{radius},{lat},{lon});
  node["amenity"](around:{radius},{lat},{lon});
);
out center 100;
"""


class OverpassScanner(BaseOsintScanner):
    scanner_name = "overpass"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.IP_ADDRESS})
    cache_ttl = 86400

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=40) as client:
            lat, lon = await self._resolve_coordinates(client, input_value, input_type)
            if lat is None or lon is None:
                return {
                    "input": input_value,
                    "found": False,
                    "error": "Could not resolve coordinates",
                    "surveillance_cameras": [],
                    "military_areas": [],
                    "government_buildings": [],
                    "pois": {},
                    "total_features": 0,
                    "extracted_identifiers": [],
                }
            return await self._query_overpass(client, lat, lon, input_value)

    async def _resolve_coordinates(
        self, client: httpx.AsyncClient, input_value: str, input_type: ScanInputType
    ) -> tuple[float | None, float | None]:
        # IP_ADDRESS input: expect "lat,lon" coordinate string directly
        if input_type == ScanInputType.IP_ADDRESS:
            try:
                parts = input_value.split(",")
                if len(parts) == 2:
                    return float(parts[0].strip()), float(parts[1].strip())
            except ValueError:
                pass
            return None, None

        # DOMAIN input: geocode as place name via Nominatim
        try:
            resp = await client.get(
                _NOMINATIM_URL,
                params={"q": input_value, "format": "json", "limit": "1"},
                headers=_NOMINATIM_HEADERS,
            )
            if resp.status_code != 200:
                return None, None
            results = resp.json()
            if not results:
                return None, None
            return float(results[0]["lat"]), float(results[0]["lon"])
        except Exception as exc:
            log.warning("Nominatim geocode failed", input=input_value, error=str(exc))
            return None, None

    async def _query_overpass(
        self, client: httpx.AsyncClient, lat: float, lon: float, original_input: str
    ) -> dict[str, Any]:
        query = _build_overpass_query(lat, lon)
        try:
            resp = await client.post(_OVERPASS_URL, data={"data": query})
            if resp.status_code != 200:
                return {
                    "input": original_input,
                    "found": False,
                    "error": f"Overpass API error: {resp.status_code}",
                    "surveillance_cameras": [],
                    "military_areas": [],
                    "government_buildings": [],
                    "pois": {},
                    "total_features": 0,
                    "extracted_identifiers": [],
                }
            data = resp.json()
        except Exception as exc:
            log.warning("Overpass query failed", lat=lat, lon=lon, error=str(exc))
            return {
                "input": original_input,
                "found": False,
                "error": str(exc),
                "surveillance_cameras": [],
                "military_areas": [],
                "government_buildings": [],
                "pois": {},
                "total_features": 0,
                "extracted_identifiers": [],
            }

        elements = data.get("elements", [])
        surveillance_cameras: list[dict[str, Any]] = []
        military_areas: list[dict[str, Any]] = []
        government_buildings: list[dict[str, Any]] = []
        pois: dict[str, list[dict[str, Any]]] = {}

        for el in elements:
            tags = el.get("tags", {})
            el_lat = el.get("lat") or el.get("center", {}).get("lat")
            el_lon = el.get("lon") or el.get("center", {}).get("lon")
            point = {"lat": el_lat, "lon": el_lon, "name": tags.get("name", ""), "osm_id": el.get("id")}

            if tags.get("man_made") == "surveillance":
                surveillance_cameras.append(point)
            elif tags.get("landuse") == "military":
                military_areas.append(point)
            elif tags.get("building") == "government":
                government_buildings.append(point)
            elif tags.get("amenity"):
                amenity = tags["amenity"]
                pois.setdefault(amenity, []).append(point)

        return {
            "input": original_input,
            "found": bool(elements),
            "center_lat": lat,
            "center_lon": lon,
            "radius_m": _RADIUS_M,
            "surveillance_cameras": surveillance_cameras,
            "military_areas": military_areas,
            "government_buildings": government_buildings,
            "pois": pois,
            "total_features": len(elements),
            "extracted_identifiers": [],
        }
