"""Geolocation Challenge Scanner — GeoGuessr-style OSINT challenge generator from coordinates.

OPSEC intelligence value:
  - Trains analysts in the discipline of geographic cue recognition (GEOINT methodology).
  - Overpass-sourced landmarks provide real ground-truth anchors without revealing exact position.
  - Climate zone and vegetation hints reflect the practitioner's workflow for narrowing a location
    from imagery without metadata — hemisphere from star trails/sun direction, Koppen zone from
    vegetation, population density from road grid density.

Input entities:  COORDINATES — "lat,lon" decimal string
Output entities:
  - challenge_hints       — ordered list of clues, progressively more specific
  - nearby_landmarks      — real OSM POI data within 1 km
  - difficulty_score      — float 0-1 (1 = hardest, uninhabited wilderness)
  - solution              — exact Nominatim reverse-geocoded location (hidden by default)
  - educational_context   — geolocation methodology notes
"""

from __future__ import annotations

import math
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_HEADERS = {"User-Agent": "OSINT-Platform/1.0 contact@example.com"}

_EDUCATIONAL_CONTEXT = (
    "Geolocation methodology (GeoGuessr OSINT approach): "
    "1) Hemisphere — sun position, star trail direction, traffic side. "
    "2) Climate zone — vegetation density, snow presence, dust/red soil. "
    "3) Language/script — signs, licence plates, writing systems. "
    "4) Infrastructure — road markings, utility pole style, building materials. "
    "5) Unique flora — palm species, cedar type, grass colour reveal latitude band. "
    "6) Population density — urban grid vs rural track vs wilderness. "
    "Combine multiple signals for triangulation confidence."
)

# Koppen-Geiger simplified lookup by latitude band and hemisphere
_KOPPEN_BY_LAT: list[tuple[float, float, str, str]] = [
    (0, 10, "Af/Am", "Tropical rainforest / monsoon"),
    (10, 20, "Aw/As", "Tropical savanna"),
    (20, 30, "BWh/BSh", "Hot desert / semi-arid"),
    (30, 40, "Csa/Cfa", "Mediterranean / humid subtropical"),
    (40, 50, "Cfb/Dfb", "Oceanic / humid continental"),
    (50, 60, "Dfc/Dfd", "Subarctic"),
    (60, 90, "ET/EF", "Tundra / Ice cap"),
]

# Vegetation zones by absolute latitude
_VEGETATION_BY_LAT: list[tuple[float, float, str]] = [
    (0, 10, "Tropical rainforest — dense canopy, high biodiversity, year-round green"),
    (10, 20, "Tropical savanna — seasonal grassland with scattered acacia/baobab"),
    (20, 30, "Subtropical desert — sparse xerophyte scrub, cacti, succulents"),
    (30, 40, "Mediterranean scrub / chaparral — drought-adapted shrubs, olive, pine"),
    (40, 55, "Temperate deciduous forest / grassland — oak, maple, wheat fields"),
    (55, 65, "Boreal taiga — dense conifer (spruce, fir, pine), peat bogs"),
    (65, 90, "Arctic tundra — dwarf shrubs, mosses, lichens; no trees"),
]


def _classify_koppen(abs_lat: float) -> tuple[str, str]:
    for lo, hi, code, label in _KOPPEN_BY_LAT:
        if lo <= abs_lat < hi:
            return code, label
    return "EF", "Ice cap"


def _classify_vegetation(abs_lat: float) -> str:
    for lo, hi, desc in _VEGETATION_BY_LAT:
        if lo <= abs_lat < hi:
            return desc
    return "Ice sheet — no vegetation"


def _hemisphere_hint(lat: float, lon: float) -> list[str]:
    hints = []
    hints.append(f"Hemisphere: {'Northern' if lat >= 0 else 'Southern'}")
    hints.append(f"Longitude zone: {'Eastern (Africa/Europe/Asia/Oceania)' if lon >= 0 else 'Western (Americas/Greenland)'}")
    if abs(lat) < 23.5:
        hints.append("Tropics: sun reaches directly overhead; shadows point both directions seasonally")
    elif abs(lat) < 66.5:
        hints.append(f"Temperate zone: shadows always point {'south' if lat > 0 else 'north'} at solar noon")
    else:
        hints.append("Polar zone: midnight sun or polar night periods")
    return hints


def _population_density_hint(pois: list[dict[str, Any]]) -> str:
    count = len(pois)
    if count == 0:
        return "Extremely remote — no nearby infrastructure found in OpenStreetMap"
    if count < 5:
        return "Rural — very sparse settlement, limited services"
    if count < 20:
        return "Semi-rural / small town — some local amenities present"
    if count < 50:
        return "Suburban or mid-sized town"
    return "Urban — dense amenity coverage, likely city centre"


def _difficulty_score(abs_lat: float, poi_count: int) -> float:
    """Higher score = harder to identify. Remote high-latitude = hardest."""
    lat_factor = min(abs_lat / 90.0, 1.0) * 0.4
    density_factor = max(0.0, 1.0 - poi_count / 50.0) * 0.6
    return round(lat_factor + density_factor, 3)


class GeolocationChallengeScanner(BaseOsintScanner):
    """Generate an educational GeoGuessr-style challenge from decimal coordinates.

    Input:  ScanInputType.COORDINATES — "lat,lon" string.
    Output: challenge_hints, nearby_landmarks, difficulty_score, solution, educational_context.
    """

    scanner_name = "geolocation_challenge"
    supported_input_types = frozenset({ScanInputType.COORDINATES})
    cache_ttl = 86400

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        lat, lon = self._parse_coordinates(input_value)
        if lat is None or lon is None:
            return self._error_result(input_value, "Invalid coordinate format. Expected 'lat,lon'.")

        abs_lat = abs(lat)
        koppen_code, koppen_label = _classify_koppen(abs_lat)
        vegetation = _classify_vegetation(abs_lat)

        async with httpx.AsyncClient(timeout=30.0, headers=_HEADERS) as client:
            solution = await self._reverse_geocode(client, lat, lon)
            landmarks = await self._fetch_landmarks(client, lat, lon)

        hints = _hemisphere_hint(lat, lon)
        hints.append(f"Climate zone (Koppen {koppen_code}): {koppen_label}")
        hints.append(f"Vegetation zone: {vegetation}")
        hints.append(_population_density_hint(landmarks))

        if solution.get("country"):
            # Add continent-level hint (not country) as penultimate clue
            hints.append(f"Continent hint: {self._country_to_continent_hint(solution.get('country_code', ''))}")

        difficulty = _difficulty_score(abs_lat, len(landmarks))

        return {
            "input": input_value,
            "found": True,
            "lat": lat,
            "lon": lon,
            "challenge_hints": hints,
            "nearby_landmarks": landmarks[:20],
            "difficulty_score": difficulty,
            "koppen_code": koppen_code,
            "koppen_label": koppen_label,
            "vegetation_zone": vegetation,
            "solution": solution,  # reveal=False in frontend by default
            "educational_context": _EDUCATIONAL_CONTEXT,
            "extracted_identifiers": [f"coordinates:{lat},{lon}"] if solution.get("country") else [],
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
    # Nominatim reverse geocode
    # ------------------------------------------------------------------

    async def _reverse_geocode(self, client: httpx.AsyncClient, lat: float, lon: float) -> dict[str, Any]:
        try:
            resp = await client.get(
                _NOMINATIM_URL,
                params={"lat": str(lat), "lon": str(lon), "format": "json", "addressdetails": "1"},
            )
            if resp.status_code != 200:
                return {}
            data = resp.json()
            address = data.get("address", {})
            return {
                "display_name": data.get("display_name", ""),
                "country": address.get("country", ""),
                "country_code": address.get("country_code", "").upper(),
                "state": address.get("state", ""),
                "city": address.get("city") or address.get("town") or address.get("village", ""),
                "postcode": address.get("postcode", ""),
                "road": address.get("road", ""),
            }
        except Exception as exc:
            log.warning("Nominatim reverse geocode failed", lat=lat, lon=lon, error=str(exc))
            return {}

    # ------------------------------------------------------------------
    # Overpass landmarks
    # ------------------------------------------------------------------

    async def _fetch_landmarks(self, client: httpx.AsyncClient, lat: float, lon: float) -> list[dict[str, Any]]:
        query = (
            f"[out:json][timeout:25];"
            f"("
            f'node["amenity"](around:1000,{lat},{lon});'
            f'node["tourism"](around:1000,{lat},{lon});'
            f'node["historic"](around:1000,{lat},{lon});'
            f'node["shop"](around:1000,{lat},{lon});'
            f");"
            f"out 50;"
        )
        try:
            resp = await client.post(_OVERPASS_URL, data={"data": query})
            if resp.status_code != 200:
                return []
            elements = resp.json().get("elements", [])
            landmarks = []
            for el in elements:
                tags = el.get("tags", {})
                name = tags.get("name", "")
                category = (
                    tags.get("amenity")
                    or tags.get("tourism")
                    or tags.get("historic")
                    or tags.get("shop")
                    or "unknown"
                )
                landmarks.append({
                    "name": name,
                    "category": category,
                    "lat": el.get("lat"),
                    "lon": el.get("lon"),
                    "osm_id": el.get("id"),
                })
            return landmarks
        except Exception as exc:
            log.warning("Overpass landmark fetch failed", lat=lat, lon=lon, error=str(exc))
            return []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _country_to_continent_hint(self, country_code: str) -> str:
        # Simplified continent map for major country codes
        _africa = {"DZ", "EG", "NG", "ZA", "KE", "ET", "GH", "TZ", "MA", "MZ", "AO", "SD", "CM", "MG", "CI", "NE", "ML", "BF", "MW", "ZM", "SN", "SO", "TD", "GN", "RW", "BJ", "TN", "BI", "SS", "TG", "ER", "SL", "MR", "CF", "LY", "CG", "MU", "LS", "GM", "BW", "NA", "GA", "GW", "GQ", "ST", "SC", "KM", "CV", "DJ"}
        _americas = {"US", "CA", "MX", "BR", "AR", "CO", "PE", "VE", "CL", "EC", "BO", "PY", "UY", "GY", "SR", "CR", "PA", "GT", "HN", "NI", "SV", "BZ", "CU", "DO", "HT", "JM", "TT", "BB", "GD", "LC", "VC", "KN", "AG", "DM", "BS"}
        _asia = {"CN", "IN", "JP", "KR", "ID", "PK", "BD", "VN", "TH", "MM", "MY", "PH", "KH", "LA", "SG", "BN", "TL", "MN", "KZ", "UZ", "TM", "KG", "TJ", "AF", "IR", "IQ", "SA", "AE", "QA", "KW", "BH", "OM", "YE", "JO", "IL", "LB", "SY", "TR", "AZ", "AM", "GE", "NP", "BT", "LK", "MV"}
        _europe = {"DE", "FR", "GB", "IT", "ES", "PL", "RO", "NL", "BE", "GR", "CZ", "SE", "PT", "HU", "AT", "BY", "CH", "BG", "RS", "DK", "FI", "SK", "NO", "IE", "HR", "BA", "AL", "LT", "SI", "MK", "LV", "EE", "ME", "LU", "MT", "IS", "AD", "MC", "LI", "SM", "VA", "UA", "MD", "RU"}
        _oceania = {"AU", "NZ", "PG", "FJ", "SB", "VU", "WS", "TO", "KI", "FM", "MH", "PW", "NR", "TV"}

        cc = country_code.upper()
        if cc in _africa:
            return "Africa"
        if cc in _americas:
            return "Americas (North or South)"
        if cc in _asia:
            return "Asia or Middle East"
        if cc in _europe:
            return "Europe"
        if cc in _oceania:
            return "Oceania / Pacific"
        return "Unknown continent"

    def _error_result(self, input_value: str, error: str) -> dict[str, Any]:
        return {
            "input": input_value,
            "found": False,
            "error": error,
            "challenge_hints": [],
            "nearby_landmarks": [],
            "difficulty_score": 0.0,
            "solution": {},
            "educational_context": _EDUCATIONAL_CONTEXT,
            "extracted_identifiers": [],
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
