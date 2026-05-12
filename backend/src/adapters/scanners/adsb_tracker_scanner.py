"""ADS-B Tracker — fetches live aircraft positions near given coordinates via OpenSky Network."""
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_OPENSKY_API_URL = "https://opensky-network.org/api/states/all"

# ADS-B state vector column indices per OpenSky API documentation
_COL_ICAO24 = 0
_COL_CALLSIGN = 1
_COL_ORIGIN_COUNTRY = 2
_COL_TIME_POSITION = 3
_COL_LAST_CONTACT = 4
_COL_LONGITUDE = 5
_COL_LATITUDE = 6
_COL_BARO_ALTITUDE = 7
_COL_ON_GROUND = 8
_COL_VELOCITY = 9
_COL_TRUE_TRACK = 10
_COL_VERTICAL_RATE = 11
_COL_SENSORS = 12
_COL_GEO_ALTITUDE = 13
_COL_SQUAWK = 14
_COL_SPI = 15
_COL_POSITION_SOURCE = 16

_POSITION_SOURCES = {0: "ADS-B", 1: "ASTERIX", 2: "MLAT", 3: "FLARM"}


def _parse_coordinates(value: str) -> tuple[float, float]:
    parts = value.strip().split(",")
    if len(parts) < 2:
        raise ValueError(f"Expected 'lat,lon' format, got: {value!r}")
    return float(parts[0].strip()), float(parts[1].strip())


def _nm_to_deg(nautical_miles: float) -> float:
    """Convert nautical miles to degrees (approximate)."""
    return nautical_miles / 60.0


def _parse_state_vector(sv: list[Any]) -> dict[str, Any]:
    """Parse a raw OpenSky state vector list into a structured dict."""
    icao24 = sv[_COL_ICAO24] if len(sv) > _COL_ICAO24 else None
    callsign_raw = sv[_COL_CALLSIGN] if len(sv) > _COL_CALLSIGN else None
    callsign = callsign_raw.strip() if isinstance(callsign_raw, str) else None

    altitude_m = sv[_COL_BARO_ALTITUDE] if len(sv) > _COL_BARO_ALTITUDE else None
    geo_altitude_m = sv[_COL_GEO_ALTITUDE] if len(sv) > _COL_GEO_ALTITUDE else None
    velocity_ms = sv[_COL_VELOCITY] if len(sv) > _COL_VELOCITY else None
    pos_src_code = sv[_COL_POSITION_SOURCE] if len(sv) > _COL_POSITION_SOURCE else None

    return {
        "icao24": icao24,
        "callsign": callsign or "N/A",
        "origin_country": sv[_COL_ORIGIN_COUNTRY] if len(sv) > _COL_ORIGIN_COUNTRY else None,
        "latitude": sv[_COL_LATITUDE] if len(sv) > _COL_LATITUDE else None,
        "longitude": sv[_COL_LONGITUDE] if len(sv) > _COL_LONGITUDE else None,
        "baro_altitude_m": altitude_m,
        "baro_altitude_ft": round(altitude_m * 3.28084, 0) if altitude_m is not None else None,
        "geo_altitude_m": geo_altitude_m,
        "on_ground": sv[_COL_ON_GROUND] if len(sv) > _COL_ON_GROUND else None,
        "velocity_ms": velocity_ms,
        "velocity_knots": round(velocity_ms * 1.94384, 1) if velocity_ms is not None else None,
        "heading_deg": sv[_COL_TRUE_TRACK] if len(sv) > _COL_TRUE_TRACK else None,
        "vertical_rate_ms": sv[_COL_VERTICAL_RATE] if len(sv) > _COL_VERTICAL_RATE else None,
        "squawk": sv[_COL_SQUAWK] if len(sv) > _COL_SQUAWK else None,
        "position_source": _POSITION_SOURCES.get(pos_src_code, str(pos_src_code)) if pos_src_code is not None else None,
        "last_contact_unix": sv[_COL_LAST_CONTACT] if len(sv) > _COL_LAST_CONTACT else None,
        "flightradar_url": f"https://www.flightradar24.com/{callsign}" if callsign else None,
        "adsbexchange_url": f"https://globe.adsbexchange.com/?icao={icao24}" if icao24 else None,
    }


class AdsbTrackerScanner(BaseOsintScanner):
    """Fetches real-time aircraft positions near coordinates via OpenSky Network free API (no auth required)."""

    scanner_name = "adsb_tracker"
    supported_input_types = frozenset({ScanInputType.COORDINATES})
    cache_ttl = 60  # Near real-time data

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        try:
            lat, lon = _parse_coordinates(input_value)
        except ValueError as exc:
            return {"found": False, "error": str(exc)}

        # 25 nautical mile bounding box (~46 km radius)
        radius_nm = 25
        delta_deg = _nm_to_deg(radius_nm)

        bbox = {
            "lamin": round(lat - delta_deg, 6),
            "lomin": round(lon - delta_deg, 6),
            "lamax": round(lat + delta_deg, 6),
            "lomax": round(lon + delta_deg, 6),
        }

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(_OPENSKY_API_URL, params=bbox)

                if resp.status_code == 429:
                    return {
                        "found": False,
                        "error": "OpenSky Network rate limit reached. Try again in 10 seconds.",
                        "coordinates": {"latitude": lat, "longitude": lon},
                    }

                resp.raise_for_status()
                data = resp.json()

        except httpx.HTTPStatusError as exc:
            return {
                "found": False,
                "error": f"OpenSky API error {exc.response.status_code}",
                "coordinates": {"latitude": lat, "longitude": lon},
            }
        except Exception as exc:
            return {"found": False, "error": f"ADS-B request failed: {exc}"}

        raw_states = data.get("states") or []
        timestamp = data.get("time")

        aircraft: list[dict[str, Any]] = []
        for sv in raw_states:
            if not isinstance(sv, list):
                continue
            parsed = _parse_state_vector(sv)
            aircraft.append(parsed)

        # Sort by velocity descending (fast aircraft first)
        aircraft.sort(key=lambda a: a.get("velocity_ms") or 0, reverse=True)

        # Categorise by type
        airborne = [a for a in aircraft if not a.get("on_ground")]
        on_ground = [a for a in aircraft if a.get("on_ground")]

        return {
            "found": bool(aircraft),
            "coordinates": {"latitude": lat, "longitude": lon},
            "search_radius_nm": radius_nm,
            "bounding_box": bbox,
            "timestamp_unix": timestamp,
            "aircraft_count": len(aircraft),
            "airborne_count": len(airborne),
            "on_ground_count": len(on_ground),
            "aircraft": aircraft,
            "data_source": "OpenSky Network (opensky-network.org) — free, no auth",
            "alternative_sources": [
                "https://globe.adsbexchange.com — uncensored ADS-B (military visible)",
                "https://www.flightradar24.com — commercial, best coverage",
                "https://planefinder.net — alternative tracker",
            ],
            "educational_note": (
                "ADS-B (Automatic Dependent Surveillance-Broadcast) is mandatory on commercial aircraft. "
                "Military and some private aircraft can disable transponders. "
                "For uncensored military tracking, use ADSBexchange which does not filter data. "
                "ICAO24 hex codes uniquely identify each aircraft registration."
            ),
        }
