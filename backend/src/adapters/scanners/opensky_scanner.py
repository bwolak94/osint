"""OpenSky Network scanner — live aircraft tracking and registration lookup."""

from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_OPENSKY_STATES_URL = "https://opensky-network.org/api/states/all"
_ADSBDB_URL = "https://api.adsbdb.com/v0/aircraft/{icao}"
_ADSBDB_CALLSIGN_URL = "https://api.adsbdb.com/v0/callsign/{callsign}"


class OpenSkyScanner(BaseOsintScanner):
    scanner_name = "opensky"
    supported_input_types = frozenset({ScanInputType.DOMAIN})
    cache_ttl = 300  # 5 minutes — live data

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        # Derive company/operator search term from domain
        company = input_value.lower().removeprefix("www.").split(".")[0]
        async with httpx.AsyncClient(timeout=20) as client:
            return await self._search_aircraft(client, company, input_value)

    async def _search_aircraft(
        self, client: httpx.AsyncClient, company: str, original_input: str
    ) -> dict[str, Any]:
        aircraft: list[dict[str, Any]] = []
        route_history: list[dict[str, Any]] = []
        owner_info: dict[str, Any] = {}

        # Query ADSB database for aircraft by operator/callsign prefix
        try:
            resp = await client.get(_ADSBDB_CALLSIGN_URL.format(callsign=company.upper()[:4]))
            if resp.status_code == 200:
                data = resp.json()
                flight_route = data.get("response", {}).get("flightroute", {})
                if flight_route:
                    airline = flight_route.get("airline", {})
                    owner_info = {
                        "airline_name": airline.get("name", ""),
                        "iata": airline.get("iata", ""),
                        "icao": airline.get("icao", ""),
                        "country": airline.get("country", ""),
                        "callsign": flight_route.get("callsign", ""),
                    }
                    route_history.append(
                        {
                            "origin": flight_route.get("origin", {}).get("iata_code", ""),
                            "destination": flight_route.get("destination", {}).get("iata_code", ""),
                        }
                    )
        except Exception as exc:
            log.warning("ADSBDB callsign lookup failed", company=company, error=str(exc))

        # Attempt live state vector lookup for a bounding box (global, limited to first 25 results)
        try:
            resp = await client.get(_OPENSKY_STATES_URL, params={"extended": "1"})
            if resp.status_code == 200:
                data = resp.json()
                states = data.get("states", []) or []
                # Filter by callsign containing company abbreviation
                prefix = company[:3].upper()
                for state in states:
                    if state and len(state) >= 8:
                        callsign = (state[1] or "").strip()
                        if callsign.startswith(prefix):
                            aircraft.append(
                                {
                                    "icao24": state[0],
                                    "callsign": callsign,
                                    "origin_country": state[2],
                                    "velocity": state[9],
                                    "altitude": state[7],
                                    "heading": state[10],
                                    "last_contact": state[4],
                                }
                            )
                        if len(aircraft) >= 25:
                            break
        except Exception as exc:
            log.warning("OpenSky states fetch failed", error=str(exc))

        return {
            "input": original_input,
            "company": company,
            "found": bool(aircraft) or bool(owner_info),
            "aircraft": aircraft,
            "route_history": route_history,
            "owner_info": owner_info,
            "extracted_identifiers": [],
        }
