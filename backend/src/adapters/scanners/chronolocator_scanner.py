"""Chronolocator — calculates sun position throughout the day to estimate photo capture time from shadows."""
import math
from datetime import date
from typing import Any

import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()


def _day_of_year(d: date) -> int:
    return d.timetuple().tm_yday


def _solar_declination(day_of_year: int) -> float:
    """Approximate solar declination in radians."""
    return math.radians(23.45 * math.sin(math.radians(360 / 365 * (day_of_year - 81))))


def _hour_angle(hour_utc: float, longitude_deg: float) -> float:
    """Hour angle in radians: 0 at solar noon."""
    solar_noon_offset = longitude_deg / 15.0  # hours
    solar_hour = hour_utc + solar_noon_offset
    return math.radians((solar_hour - 12) * 15)


def _sun_position(lat_deg: float, lon_deg: float, hour_utc: float, day_of_year: int) -> dict[str, float | None]:
    """Returns azimuth (degrees N clockwise) and elevation (degrees) for given lat/lon/time."""
    lat = math.radians(lat_deg)
    decl = _solar_declination(day_of_year)
    ha = _hour_angle(hour_utc, lon_deg)

    sin_elev = (
        math.sin(lat) * math.sin(decl)
        + math.cos(lat) * math.cos(decl) * math.cos(ha)
    )
    elevation = math.degrees(math.asin(max(-1.0, min(1.0, sin_elev))))

    cos_elev = math.cos(math.asin(max(-1.0, min(1.0, sin_elev))))
    if cos_elev < 1e-10:
        azimuth = 0.0
    else:
        cos_az_num = math.sin(decl) - math.sin(lat) * sin_elev
        cos_az = cos_az_num / (math.cos(lat) * cos_elev)
        az_rad = math.acos(max(-1.0, min(1.0, cos_az)))
        azimuth = math.degrees(az_rad)
        if math.sin(ha) > 0:
            azimuth = 360 - azimuth

    # Shadow length ratio for 1m object; undefined when sun is below horizon
    shadow_ratio: float | None
    if elevation > 0.5:
        shadow_ratio = round(1.0 / math.tan(math.radians(elevation)), 3)
    else:
        shadow_ratio = None

    # Shadow direction is opposite to sun azimuth
    shadow_direction = round((azimuth + 180) % 360, 1)

    return {
        "elevation_deg": round(elevation, 2),
        "azimuth_deg": round(azimuth, 2),
        "shadow_length_ratio": shadow_ratio,  # L = H * ratio (for object height H)
        "shadow_direction_deg": shadow_direction,
    }


def _sunrise_sunset(lat_deg: float, lon_deg: float, day_of_year: int) -> dict[str, str]:
    """Approximate sunrise/sunset in UTC hours using geometric formula."""
    lat = math.radians(lat_deg)
    decl = _solar_declination(day_of_year)
    cos_ha = -math.tan(lat) * math.tan(decl)
    if cos_ha >= 1:
        return {"sunrise_utc": "No sunrise (polar night)", "sunset_utc": "No sunset"}
    if cos_ha <= -1:
        return {"sunrise_utc": "No sunrise (midnight sun)", "sunset_utc": "No sunset"}
    ha_deg = math.degrees(math.acos(cos_ha))
    noon_utc = 12 - lon_deg / 15.0
    sunrise_h = noon_utc - ha_deg / 15
    sunset_h = noon_utc + ha_deg / 15

    def fmt(h: float) -> str:
        h = h % 24
        return f"{int(h):02d}:{int((h % 1) * 60):02d} UTC"

    return {"sunrise_utc": fmt(sunrise_h), "sunset_utc": fmt(sunset_h)}


class ChronolocatorScanner(BaseOsintScanner):
    """Computes sun position throughout the day to help estimate photo capture time from shadow analysis."""

    scanner_name = "chronolocator"
    supported_input_types = frozenset({ScanInputType.COORDINATES})
    cache_ttl = 3600

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        parts = input_value.strip().split(",")
        if len(parts) < 2:
            return {"found": False, "error": "Expected 'lat,lon' or 'lat,lon,YYYY-MM-DD'"}
        try:
            lat = float(parts[0].strip())
            lon = float(parts[1].strip())
        except ValueError:
            return {"found": False, "error": "Invalid latitude/longitude"}

        # Optional date argument
        if len(parts) >= 3:
            try:
                d = date.fromisoformat(parts[2].strip())
            except ValueError:
                d = date.today()
        else:
            d = date.today()

        doy = _day_of_year(d)

        # Compute sun position every 30 minutes from 04:00 to 22:00 UTC
        timeline: list[dict[str, Any]] = []
        hour = 4.0
        while hour <= 22.0:
            pos = _sun_position(lat, lon, hour, doy)
            h_int = int(hour)
            m_int = int((hour % 1) * 60)
            timeline.append({
                "time_utc": f"{h_int:02d}:{m_int:02d}",
                **pos,
            })
            hour += 0.5

        sun_times = _sunrise_sunset(lat, lon, doy)

        # Find solar noon (max elevation)
        above_horizon = [e for e in timeline if isinstance(e.get("elevation_deg"), float) and e["elevation_deg"] > 0]
        solar_noon_entry: dict[str, Any] | None = (
            max(above_horizon, key=lambda e: e["elevation_deg"])
            if above_horizon
            else None
        )

        return {
            "found": True,
            "coordinates": {"latitude": lat, "longitude": lon},
            "date": d.isoformat(),
            "day_of_year": doy,
            "sunrise_utc": sun_times["sunrise_utc"],
            "sunset_utc": sun_times["sunset_utc"],
            "solar_noon": solar_noon_entry,
            "sun_timeline": timeline,
            "formula_note": "Shadow length L = H x cot(a) where H is object height and a is sun elevation angle.",
            "educational_note": (
                "By measuring shadow length and direction in a photo, analysts can triangulate the approximate "
                "time and date of capture. Cross-reference with local timezone to get local time."
            ),
        }
