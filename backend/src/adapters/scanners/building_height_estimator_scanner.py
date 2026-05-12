"""Building Height Estimator Scanner — shadow-based height calculation + OSM building data.

OPSEC intelligence value:
  - Shadow-length geometry (chronolocation technique) estimates a building's height from
    its shadow in open-source imagery when sun elevation at capture time is known.
  - Formula: H = shadow_length_m * tan(sun_elevation_rad)
  - Cross-referencing calculated height with OSM building:height tags validates the estimate
    and may confirm the specific building's identity.
  - Useful for confirming whether a facility visible in imagery matches known dimensions of
    a suspect structure, or for estimating floor count (approx. 3–4 m/floor).

Input entities:  COORDINATES — "lat,lon[,date,time_utc,shadow_length_m]"
  - Minimal: "lat,lon"
  - Full:    "lat,lon,2024-06-15,14:30,42.5"
    where date is YYYY-MM-DD, time_utc is HH:MM, shadow_length_m is float

Output entities:
  - calculated_height_m   — height derived from shadow formula (if shadow_length provided)
  - nearby_buildings      — OSM buildings with height/levels tags within 100 m
  - sun_elevation_degrees — computed solar elevation for specified or current date/time
  - formula_explanation   — step-by-step derivation
  - educational_note      — chronolocation + shadow-based height methodology
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_HEADERS = {"User-Agent": "OSINT-Platform/1.0 contact@example.com"}

_EDUCATIONAL_NOTE = (
    "Shadow-based building height (IMINT/GEOINT technique): "
    "Formula: H = L * tan(α), where L = shadow length in metres, α = sun elevation angle. "
    "Sun elevation can be determined from: "
    "1) Shadow direction + known date/location → solar position algorithms (NREL SPA). "
    "2) EXIF timestamp + GPS coordinates → compute sun elevation directly. "
    "3) Reference object of known height in same image → calibrate shadow scale factor. "
    "Floor count estimation: each floor ≈ 3.0–3.5 m for residential, 4.0 m for commercial. "
    "Uncertainty note: shadow length must account for terrain slope and is measured at the "
    "shadow tip (not the building base projection on flat terrain)."
)

_FORMULA_EXPLANATION = (
    "Step 1: Determine sun elevation angle α at the capture location and time. "
    "Step 2: Measure shadow length L from building base to shadow tip (in metres; "
    "calibrate using known reference objects or image GSD). "
    "Step 3: Apply formula H = L × tan(α). "
    "Step 4: Cross-check with nearby OSM building:height tag or floor count × avg floor height. "
    "Caveat: formula assumes flat terrain — apply correction for slope if terrain model available."
)


def _solar_elevation(lat_deg: float, lon_deg: float, dt: datetime) -> float:
    """Compute solar elevation angle in degrees for given location and UTC datetime.

    Uses the simplified Spencer / Blanco-Muriel solar position algorithm.
    Accuracy: ±0.5 degrees for most dates and locations.
    """
    # Day of year
    doy = dt.timetuple().tm_yday
    hour_utc = dt.hour + dt.minute / 60.0 + dt.second / 3600.0

    # Equation of time and solar declination (Spencer's formula)
    B = 2 * math.pi * (doy - 1) / 365.0
    decl = (
        0.006918
        - 0.399912 * math.cos(B)
        + 0.070257 * math.sin(B)
        - 0.006758 * math.cos(2 * B)
        + 0.000907 * math.sin(2 * B)
        - 0.002697 * math.cos(3 * B)
        + 0.00148 * math.sin(3 * B)
    )

    # Equation of time (minutes)
    eot = 229.18 * (
        0.000075
        + 0.001868 * math.cos(B)
        - 0.032077 * math.sin(B)
        - 0.014615 * math.cos(2 * B)
        - 0.04089 * math.sin(2 * B)
    )

    # Solar time
    time_offset = eot + 4 * lon_deg  # minutes
    solar_time = hour_utc * 60 + time_offset  # minutes since midnight
    hour_angle = math.radians((solar_time / 4) - 180)

    lat_rad = math.radians(lat_deg)

    # Solar elevation
    sin_elev = (
        math.sin(lat_rad) * math.sin(decl)
        + math.cos(lat_rad) * math.cos(decl) * math.cos(hour_angle)
    )
    elevation_deg = math.degrees(math.asin(max(-1.0, min(1.0, sin_elev))))
    return round(elevation_deg, 2)


def _estimate_height(shadow_m: float, elevation_deg: float) -> float | None:
    """Apply shadow-height formula. Returns None if sun below horizon."""
    if elevation_deg <= 0:
        return None
    return round(shadow_m * math.tan(math.radians(elevation_deg)), 2)


def _floor_count_estimate(height_m: float) -> dict[str, int]:
    return {
        "residential_floors_3m": max(1, round(height_m / 3.0)),
        "commercial_floors_4m": max(1, round(height_m / 4.0)),
    }


class BuildingHeightEstimatorScanner(BaseOsintScanner):
    """Estimate building height from shadow length and solar position + OSM data.

    Input:  ScanInputType.COORDINATES — "lat,lon[,YYYY-MM-DD,HH:MM,shadow_m]" string.
    Output: calculated_height_m, nearby_buildings, sun_elevation_degrees.
    """

    scanner_name = "building_height_estimator"
    supported_input_types = frozenset({ScanInputType.COORDINATES})
    cache_ttl = 86400

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        parsed = self._parse_input(input_value)
        if parsed is None:
            return self._error_result(input_value, "Invalid input. Expected 'lat,lon' or 'lat,lon,YYYY-MM-DD,HH:MM,shadow_m'.")

        lat, lon, date_str, time_str, shadow_m = parsed

        # Determine datetime for solar calculation
        if date_str and time_str:
            try:
                dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
            except ValueError:
                dt = datetime.now(timezone.utc)
        else:
            dt = datetime.now(timezone.utc)

        sun_elevation = _solar_elevation(lat, lon, dt)

        # Shadow-based height
        calculated_height: float | None = None
        floor_estimates: dict[str, int] = {}
        if shadow_m is not None:
            calculated_height = _estimate_height(shadow_m, sun_elevation)
            if calculated_height is not None:
                floor_estimates = _floor_count_estimate(calculated_height)

        # OSM building data
        nearby_buildings = await self._fetch_osm_buildings(lat, lon)

        return {
            "input": input_value,
            "found": True,
            "lat": lat,
            "lon": lon,
            "analysis_datetime_utc": dt.isoformat(),
            "sun_elevation_degrees": sun_elevation,
            "shadow_length_m": shadow_m,
            "calculated_height_m": calculated_height,
            "floor_count_estimates": floor_estimates,
            "nearby_buildings": nearby_buildings,
            "formula_explanation": _FORMULA_EXPLANATION,
            "educational_note": _EDUCATIONAL_NOTE,
            "extracted_identifiers": [f"coordinates:{lat},{lon}"],
        }

    # ------------------------------------------------------------------
    # Input parsing
    # ------------------------------------------------------------------

    def _parse_input(
        self, value: str
    ) -> tuple[float, float, str | None, str | None, float | None] | None:
        """Parse 'lat,lon[,date,time_utc,shadow_m]'."""
        try:
            parts = [p.strip() for p in value.strip().split(",")]
            if len(parts) < 2:
                return None
            lat = float(parts[0])
            lon = float(parts[1])
            if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                return None
            date_str = parts[2] if len(parts) > 2 else None
            time_str = parts[3] if len(parts) > 3 else None
            shadow_m = float(parts[4]) if len(parts) > 4 else None
            return lat, lon, date_str, time_str, shadow_m
        except (ValueError, IndexError):
            return None

    # ------------------------------------------------------------------
    # OSM building fetch via Overpass
    # ------------------------------------------------------------------

    async def _fetch_osm_buildings(self, lat: float, lon: float) -> list[dict[str, Any]]:
        query = (
            f"[out:json][timeout:25];"
            f"("
            f'way["building"]["height"](around:100,{lat},{lon});'
            f'way["building"]["building:levels"](around:100,{lat},{lon});'
            f'node["building"]["height"](around:100,{lat},{lon});'
            f");"
            f"out center 20;"
        )
        try:
            async with httpx.AsyncClient(timeout=30.0, headers=_HEADERS) as client:
                resp = await client.post(_OVERPASS_URL, data={"data": query})
                if resp.status_code != 200:
                    return []
                elements = resp.json().get("elements", [])
                buildings: list[dict[str, Any]] = []
                for el in elements:
                    tags = el.get("tags", {})
                    center = el.get("center", {})
                    height_str = tags.get("height", "")
                    levels_str = tags.get("building:levels", "")
                    try:
                        height_m = float(height_str.replace("m", "").strip()) if height_str else None
                    except ValueError:
                        height_m = None
                    try:
                        levels = int(levels_str) if levels_str else None
                    except ValueError:
                        levels = None
                    estimated_from_levels = round(levels * 3.5, 1) if levels and height_m is None else None
                    buildings.append({
                        "osm_id": el.get("id"),
                        "name": tags.get("name", ""),
                        "height_m": height_m,
                        "building_levels": levels,
                        "estimated_height_from_levels_m": estimated_from_levels,
                        "lat": center.get("lat") or el.get("lat"),
                        "lon": center.get("lon") or el.get("lon"),
                    })
                return buildings
        except Exception as exc:
            log.warning("OSM building fetch failed", lat=lat, lon=lon, error=str(exc))
            return []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _error_result(self, input_value: str, error: str) -> dict[str, Any]:
        return {
            "input": input_value,
            "found": False,
            "error": error,
            "sun_elevation_degrees": None,
            "calculated_height_m": None,
            "floor_count_estimates": {},
            "nearby_buildings": [],
            "formula_explanation": _FORMULA_EXPLANATION,
            "educational_note": _EDUCATIONAL_NOTE,
            "extracted_identifiers": [],
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
