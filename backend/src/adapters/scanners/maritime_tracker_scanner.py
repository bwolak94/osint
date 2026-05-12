"""Maritime Tracker — discovers vessels near coordinates via AIS data sources."""
import os
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_MARINE_TRAFFIC_API_URL = "https://services.marinetraffic.com/api/getvessel/v:3"
_VESSELFINDER_URL = "https://www.vesselfinder.com/api/pub/vesselsonmap"

# AIS vessel type codes (ITU / IMO standard)
_VESSEL_TYPE_NAMES: dict[int, str] = {
    0: "Not available",
    20: "Wing in ground (WIG)",
    21: "WIG - Hazardous category A",
    30: "Fishing",
    31: "Towing",
    32: "Towing (large)",
    33: "Dredging / underwater ops",
    34: "Diving ops",
    35: "Military ops",
    36: "Sailing",
    37: "Pleasure craft",
    40: "High speed craft (HSC)",
    50: "Pilot vessel",
    51: "Search and Rescue",
    52: "Tug",
    53: "Port tender",
    54: "Anti-pollution equipment",
    55: "Law enforcement",
    60: "Passenger",
    70: "Cargo",
    71: "Cargo - Hazardous cat A",
    72: "Cargo - Hazardous cat B",
    80: "Tanker",
    81: "Tanker - Hazardous cat A",
    89: "Tanker - no additional info",
    90: "Other",
}


def _parse_coordinates(value: str) -> tuple[float, float]:
    parts = value.strip().split(",")
    if len(parts) < 2:
        raise ValueError(f"Expected 'lat,lon' format, got: {value!r}")
    return float(parts[0].strip()), float(parts[1].strip())


def _vessel_type_name(type_code: int | None) -> str:
    if type_code is None:
        return "Unknown"
    # Vessel types are sometimes grouped (e.g., 70-79 all cargo)
    if type_code in _VESSEL_TYPE_NAMES:
        return _VESSEL_TYPE_NAMES[type_code]
    base = (type_code // 10) * 10
    return _VESSEL_TYPE_NAMES.get(base, f"Type {type_code}")


class MaritimeTrackerScanner(BaseOsintScanner):
    """Tracks vessels near given coordinates via AIS data sources (MarineTraffic API or public endpoints)."""

    scanner_name = "maritime_tracker"
    supported_input_types = frozenset({ScanInputType.COORDINATES})
    cache_ttl = 300

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        try:
            lat, lon = _parse_coordinates(input_value)
        except ValueError as exc:
            return {"found": False, "error": str(exc)}

        api_key = os.getenv("MARINE_TRAFFIC_API_KEY")

        # Bounding box — approximately 50 nautical mile radius
        delta = 0.833  # ~50nm in degrees
        bbox = {
            "min_lat": round(lat - delta, 6),
            "min_lon": round(lon - delta, 6),
            "max_lat": round(lat + delta, 6),
            "max_lon": round(lon + delta, 6),
        }

        vessels: list[dict[str, Any]] = []
        api_used = "none"
        error_msg: str | None = None

        # Path 1: MarineTraffic commercial API
        if api_key:
            try:
                params = {
                    "v": 3,
                    "apikey": api_key,
                    "minlat": bbox["min_lat"],
                    "minlon": bbox["min_lon"],
                    "maxlat": bbox["max_lat"],
                    "maxlon": bbox["max_lon"],
                    "protocol": "jsono",
                }
                async with httpx.AsyncClient(timeout=20) as client:
                    resp = await client.get(_MARINE_TRAFFIC_API_URL, params=params)
                    resp.raise_for_status()
                    data = resp.json()

                for v in data[:30]:
                    type_code = v.get("SHIP_TYPE")
                    vessels.append({
                        "mmsi": v.get("MMSI"),
                        "imo": v.get("IMO"),
                        "name": v.get("SHIPNAME"),
                        "callsign": v.get("CALLSIGN"),
                        "flag": v.get("FLAG"),
                        "vessel_type_code": type_code,
                        "vessel_type": _vessel_type_name(int(type_code) if type_code else None),
                        "latitude": v.get("LAT"),
                        "longitude": v.get("LON"),
                        "speed_knots": v.get("SPEED"),
                        "course_deg": v.get("COURSE"),
                        "heading_deg": v.get("HEADING"),
                        "status": v.get("STATUS"),
                        "destination": v.get("DESTINATION"),
                        "eta": v.get("ETA"),
                        "draught": v.get("DRAUGHT"),
                        "last_position_utc": v.get("LAST_POS"),
                        "marinetraffic_url": f"https://www.marinetraffic.com/en/ais/details/ships/mmsi:{v.get('MMSI')}",
                    })
                api_used = "marinetraffic_api"
                log.info("maritime_tracker: MarineTraffic returned vessels", count=len(vessels))

            except Exception as exc:
                error_msg = f"MarineTraffic API failed: {exc}"
                log.warning("maritime_tracker: MarineTraffic request failed", error=str(exc))

        # Path 2: VesselFinder public map endpoint (no auth, limited data)
        if not vessels:
            try:
                vf_params = {
                    "minlat": bbox["min_lat"],
                    "minlon": bbox["min_lon"],
                    "maxlat": bbox["max_lat"],
                    "maxlon": bbox["max_lon"],
                    "zoom": 9,
                }
                async with httpx.AsyncClient(
                    timeout=15,
                    headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.vesselfinder.com/"},
                ) as client:
                    resp = await client.get(_VESSELFINDER_URL, params=vf_params)
                    if resp.status_code == 200:
                        vf_data = resp.json()
                        for entry in (vf_data if isinstance(vf_data, list) else [])[:30]:
                            if not isinstance(entry, list) or len(entry) < 8:
                                continue
                            vessels.append({
                                "mmsi": entry[0] if len(entry) > 0 else None,
                                "name": entry[1] if len(entry) > 1 else None,
                                "latitude": entry[2] / 600000.0 if isinstance(entry[2], int) else entry[2],
                                "longitude": entry[3] / 600000.0 if isinstance(entry[3], int) else entry[3],
                                "course_deg": entry[4] if len(entry) > 4 else None,
                                "speed_knots": entry[5] / 10.0 if isinstance(entry[5], (int, float)) else None,
                                "vessel_type_code": entry[7] if len(entry) > 7 else None,
                                "vessel_type": _vessel_type_name(entry[7] if len(entry) > 7 else None),
                                "flag": None,
                                "marinetraffic_url": (
                                    f"https://www.marinetraffic.com/en/ais/details/ships/mmsi:{entry[0]}"
                                    if entry[0] else None
                                ),
                            })
                        api_used = "vesselfinder_public"
                        error_msg = None
                        log.info("maritime_tracker: VesselFinder returned vessels", count=len(vessels))
            except Exception as exc:
                if not error_msg:
                    error_msg = f"VesselFinder public endpoint failed: {exc}"
                log.warning("maritime_tracker: VesselFinder request failed", error=str(exc))

        # Build extracted identifiers
        extracted_identifiers: list[str] = []
        for v in vessels:
            if v.get("mmsi"):
                extracted_identifiers.append(f"mmsi:{v['mmsi']}")
            if v.get("imo"):
                extracted_identifiers.append(f"imo:{v['imo']}")

        manual_links = [
            {
                "service": "MarineTraffic Live Map",
                "url": f"https://www.marinetraffic.com/en/ais/home/centerx:{lon}/centery:{lat}/zoom:10",
                "description": "Live AIS vessel positions (requires account for details)",
            },
            {
                "service": "VesselFinder",
                "url": f"https://www.vesselfinder.com/?lat={lat}&lon={lon}&zoom=9",
                "description": "Free vessel tracking with live AIS data",
            },
            {
                "service": "MyShipTracking",
                "url": f"https://www.myshiptracking.com/?lat={lat}&lng={lon}&zoom=9",
                "description": "Free global vessel tracking",
            },
            {
                "service": "AISstream.io",
                "url": "https://aisstream.io",
                "description": "Free WebSocket AIS stream API — real-time vessel data",
            },
            {
                "service": "Global Fishing Watch",
                "url": f"https://globalfishingwatch.org/map/?latitude={lat}&longitude={lon}&zoom=9",
                "description": "Fishing vessel monitoring and dark vessel detection",
            },
        ]

        return {
            "found": bool(vessels),
            "coordinates": {"latitude": lat, "longitude": lon},
            "search_radius_nm": 50,
            "bounding_box": bbox,
            "vessel_count": len(vessels),
            "vessels": vessels,
            "api_used": api_used,
            "error": error_msg,
            "manual_links": manual_links,
            "extracted_identifiers": extracted_identifiers,
            "educational_note": (
                "AIS (Automatic Identification System) is mandatory on vessels >300 GT and all passenger ships. "
                "Vessels can disable AIS — known as 'going dark' — which is a red flag for sanctions evasion, "
                "illegal fishing, or illicit cargo transfer. Cross-reference with Global Fishing Watch for anomaly detection. "
                "Set MARINE_TRAFFIC_API_KEY for full vessel details including port history."
            ),
        }
