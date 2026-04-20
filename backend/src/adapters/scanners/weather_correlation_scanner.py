"""Weather Correlation — fetches historical weather data for coordinates to verify photo/event conditions."""
from datetime import date, timedelta
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# WMO weather interpretation codes
_WMO_CODES: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def _parse_coordinates(value: str) -> tuple[float, float]:
    parts = value.strip().split(",")
    if len(parts) < 2:
        raise ValueError(f"Expected 'lat,lon' format, got: {value!r}")
    return float(parts[0].strip()), float(parts[1].strip())


class WeatherCorrelationScanner(BaseOsintScanner):
    """Fetches 7-day historical weather from Open-Meteo to correlate with events, photos, or media."""

    scanner_name = "weather_correlation"
    supported_input_types = frozenset({ScanInputType.COORDINATES})
    cache_ttl = 3600

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        try:
            lat, lon = _parse_coordinates(input_value)
        except ValueError as exc:
            return {"found": False, "error": str(exc)}

        end_date = date.today() - timedelta(days=1)  # Yesterday (archive lags 1 day)
        start_date = end_date - timedelta(days=6)   # 7-day window

        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "daily": ",".join([
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_sum",
                "windspeed_10m_max",
                "weathercode",
                "sunrise",
                "sunset",
            ]),
            "timezone": "UTC",
        }

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(_OPEN_METEO_ARCHIVE_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            return {
                "found": False,
                "error": f"Open-Meteo API error {exc.response.status_code}: {exc.response.text[:200]}",
            }
        except Exception as exc:
            return {"found": False, "error": f"Weather API request failed: {exc}"}

        daily = data.get("daily", {})
        dates: list[str] = daily.get("time", [])
        temp_max: list[float | None] = daily.get("temperature_2m_max", [])
        temp_min: list[float | None] = daily.get("temperature_2m_min", [])
        precip: list[float | None] = daily.get("precipitation_sum", [])
        wind_max: list[float | None] = daily.get("windspeed_10m_max", [])
        weather_codes: list[int | None] = daily.get("weathercode", [])
        sunrises: list[str] = daily.get("sunrise", [])
        sunsets: list[str] = daily.get("sunset", [])

        weather_records: list[dict[str, Any]] = []
        for i, day_str in enumerate(dates):
            wcode = weather_codes[i] if i < len(weather_codes) else None
            weather_records.append({
                "date": day_str,
                "temperature_max_c": temp_max[i] if i < len(temp_max) else None,
                "temperature_min_c": temp_min[i] if i < len(temp_min) else None,
                "precipitation_mm": precip[i] if i < len(precip) else None,
                "wind_max_kmh": wind_max[i] if i < len(wind_max) else None,
                "weather_code": wcode,
                "weather_description": _WMO_CODES.get(int(wcode), f"Unknown code {wcode}") if wcode is not None else None,
                "sunrise_utc": sunrises[i] if i < len(sunrises) else None,
                "sunset_utc": sunsets[i] if i < len(sunsets) else None,
            })

        # Summary statistics
        valid_precip = [p for p in precip if p is not None]
        valid_temps_max = [t for t in temp_max if t is not None]
        summary: dict[str, Any] = {
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "total_precipitation_mm": round(sum(valid_precip), 2) if valid_precip else None,
            "avg_temp_max_c": round(sum(valid_temps_max) / len(valid_temps_max), 1) if valid_temps_max else None,
        }

        return {
            "found": bool(weather_records),
            "coordinates": {"latitude": lat, "longitude": lon},
            "timezone": "UTC",
            "daily_records": weather_records,
            "summary": summary,
            "data_source": "Open-Meteo ERA5 Archive (free, no API key required)",
            "educational_note": (
                "Historical weather data can verify or refute claimed photo/video dates. "
                "If a photo claims to show a sunny day but weather records show heavy rain, "
                "the metadata or caption may be falsified. Cross-reference with WeatherUnderground for station-level data."
            ),
        }
