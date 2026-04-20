"""Historical Map Overlay Scanner — historical cartographic sources for a coordinate region.

OPSEC intelligence value:
  - Historical maps reveal prior land use: former military bases, industrial sites, or tunnels
    that may not appear on modern maps but still affect physical infrastructure.
  - Urban change analysis by overlaying maps from different decades shows when buildings were
    constructed, demolished, or repurposed — useful for establishing presence of a target
    facility or infrastructure at a specific historical date.
  - Old property boundaries and road alignments visible in historical maps explain anomalies
    in modern satellite imagery (subsidence, vegetation patterns, soil discoloration).
  - Wartime maps (WWII, Cold War) often show bunker systems, airfields, and depots that were
    subsequently demolished or covered but may still exhibit surface signatures.

Input entities:  COORDINATES — "lat,lon" decimal string
Output entities:
  - historical_maps  — list of maps with title, year, publisher, preview_url, viewer_url
  - time_span        — earliest to latest year covered in results
  - count            — total maps found
  - manual_urls      — direct links to viewer interfaces
  - educational_note — urban change analysis methodology
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_OLDMAPS_API_URL = "https://www.oldmapsonline.org/api/search"
_DAVID_RUMSEY_URL = "https://www.davidrumsey.com/luna/servlet/iiif/search"
_HEADERS = {"User-Agent": "OSINT-Platform/1.0 contact@example.com"}

_EDUCATIONAL_NOTE = (
    "Historical map analysis for OSINT/IMINT: "
    "1) Temporal change detection — compare map series (1940s, 1960s, 1990s, present) to "
    "   identify when infrastructure appeared or was removed. "
    "2) Military/industrial legacy — former airfields, depots, and factories appear in wartime "
    "   maps; soil contamination patterns often persist in modern multispectral imagery. "
    "3) Underground infrastructure — pre-war city plans may show tunnels, sewers, and "
    "   catacombs since sealed but physically still present. "
    "4) Property record correlation — historical cadastral maps link land parcels to owners, "
    "   enabling corporate genealogy research for target entities. "
    "5) Toponymy intelligence — historical place names on old maps can reveal cultural "
    "   affiliation, administrative history, or identify now-renamed localities. "
    "Tools: OldMapsOnline aggregates 500K+ historical maps; David Rumsey collection focuses "
    "on rare pre-1900 cartography; National Libraries often provide regional georeferenced maps."
)

_COORD_BUFFER = 0.1  # degrees buffer for bounding box


def _build_bounding_box(lat: float, lon: float, buf: float = _COORD_BUFFER) -> dict[str, float]:
    return {
        "west": lon - buf,
        "south": lat - buf,
        "east": lon + buf,
        "north": lat + buf,
    }


def _build_manual_urls(lat: float, lon: float, bbox: dict[str, float]) -> dict[str, str]:
    bbox_str = f"{bbox['west']},{bbox['south']},{bbox['east']},{bbox['north']}"
    return {
        "oldmaps_online": f"https://www.oldmapsonline.org/#bbox={bbox_str}&q=",
        "david_rumsey": (
            f"https://www.davidrumsey.com/luna/servlet/view/search?"
            f"q=type%3Aimage&sort=pub_list_no_initialsort%2Cpub_date%2Cpub_list_no%2Cseries_no"
            f"&geo=BBOX:{bbox['west']},{bbox['south']},{bbox['east']},{bbox['north']}"
        ),
        "national_library_poland": f"https://polona.pl/search/?query=mapa&filters=category%3Amaps",
        "old_maps_us_usgs": f"https://ngmdb.usgs.gov/topoview/viewer/#7/{lat}/{lon}/",
        "british_library_maps": f"https://maps.nls.uk/geo/explore/#zoom=14&lat={lat}&lon={lon}&layers=0&b=1",
        "german_historical_maps": f"https://www.digimap.ed.ac.uk/",
        "wms_openhistoricalmap": (
            f"https://openhistoricalmap.org/#map=14/{lat}/{lon}"
        ),
    }


class HistoricalMapOverlayScanner(BaseOsintScanner):
    """Aggregate historical map sources for a coordinate region.

    Input:  ScanInputType.COORDINATES — "lat,lon" string.
    Output: historical_maps list, time_span, count, manual_urls dict.
    """

    scanner_name = "historical_map_overlay"
    supported_input_types = frozenset({ScanInputType.COORDINATES})
    cache_ttl = 86400

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        lat, lon = self._parse_coordinates(input_value)
        if lat is None or lon is None:
            return self._error_result(input_value, "Invalid coordinate format. Expected 'lat,lon'.")

        bbox = _build_bounding_box(lat, lon)
        manual_urls = _build_manual_urls(lat, lon, bbox)

        async with httpx.AsyncClient(timeout=20.0, headers=_HEADERS) as client:
            oldmaps_results = await self._query_oldmaps_online(client, bbox)
            rumsey_results = await self._query_david_rumsey(client, lat, lon)

        all_maps = oldmaps_results + rumsey_results
        all_maps.sort(key=lambda m: m.get("year") or 9999)

        years = [m["year"] for m in all_maps if m.get("year")]
        time_span = {
            "earliest": min(years) if years else None,
            "latest": max(years) if years else None,
        }

        return {
            "input": input_value,
            "found": len(all_maps) > 0,
            "lat": lat,
            "lon": lon,
            "historical_maps": all_maps[:30],
            "total_found": len(all_maps),
            "time_span": time_span,
            "manual_urls": manual_urls,
            "educational_note": _EDUCATIONAL_NOTE,
            "extracted_identifiers": [f"coordinates:{lat},{lon}"],
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
    # OldMapsOnline.org
    # ------------------------------------------------------------------

    async def _query_oldmaps_online(
        self, client: httpx.AsyncClient, bbox: dict[str, float]
    ) -> list[dict[str, Any]]:
        """Query OldMapsOnline BBOX search API."""
        params = {
            "bbox": f"{bbox['west']},{bbox['south']},{bbox['east']},{bbox['north']}",
            "output": "json",
            "rows": "50",
        }
        try:
            resp = await client.get(_OLDMAPS_API_URL, params=params)
            if resp.status_code != 200:
                log.warning("OldMapsOnline API error", status=resp.status_code)
                return []
            data = resp.json()
            docs = data.get("response", {}).get("docs", [])
            results: list[dict[str, Any]] = []
            for doc in docs:
                title = doc.get("title", doc.get("dc_title", "Unknown map"))
                year_str = doc.get("date", doc.get("dc_date", ""))
                year = self._extract_year(year_str)
                results.append({
                    "source": "oldmapsonline",
                    "title": title,
                    "year": year,
                    "publisher": doc.get("publisher", doc.get("dc_publisher", "")),
                    "scale": doc.get("scale", ""),
                    "preview_url": doc.get("thumbnail", doc.get("smapshot_thumbnail", "")),
                    "viewer_url": doc.get("link", doc.get("dc_identifier", "")),
                    "id": doc.get("id", ""),
                })
            return results
        except Exception as exc:
            log.warning("OldMapsOnline query failed", error=str(exc))
            return []

    # ------------------------------------------------------------------
    # David Rumsey Map Collection
    # ------------------------------------------------------------------

    async def _query_david_rumsey(
        self, client: httpx.AsyncClient, lat: float, lon: float
    ) -> list[dict[str, Any]]:
        """Query David Rumsey IIIF search endpoint."""
        # David Rumsey IIIF search — free text query with location context
        query = f"lat:{round(lat, 1)} lon:{round(lon, 1)}"
        params = {
            "q": query,
            "format": "json",
            "limit": "20",
        }
        try:
            resp = await client.get(_DAVID_RUMSEY_URL, params=params)
            if resp.status_code != 200:
                log.warning("David Rumsey API error", status=resp.status_code)
                return []
            data = resp.json()
            manifests = data.get("manifests", []) or data.get("resources", [])
            results: list[dict[str, Any]] = []
            for m in manifests:
                label = m.get("label", "")
                if isinstance(label, list):
                    label = " ".join(str(x) for x in label)
                metadata_list = m.get("metadata", [])
                meta: dict[str, str] = {}
                for item in metadata_list:
                    k = str(item.get("label", ""))
                    v = item.get("value", "")
                    if isinstance(v, list):
                        v = " ".join(str(x) for x in v)
                    meta[k] = str(v)
                year_str = meta.get("Date", meta.get("date", ""))
                year = self._extract_year(year_str)
                results.append({
                    "source": "david_rumsey",
                    "title": label or meta.get("Title", "Unknown"),
                    "year": year,
                    "publisher": meta.get("Author", meta.get("Publisher", "")),
                    "scale": meta.get("Scale", ""),
                    "preview_url": m.get("thumbnail", {}).get("@id", "") if isinstance(m.get("thumbnail"), dict) else "",
                    "viewer_url": m.get("@id", ""),
                    "id": m.get("@id", ""),
                })
            return results
        except Exception as exc:
            log.warning("David Rumsey query failed", error=str(exc))
            return []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _extract_year(self, date_str: str) -> int | None:
        """Extract first 4-digit year from a date string."""
        import re
        if not date_str:
            return None
        match = re.search(r"\b(1[0-9]{3}|20[0-2][0-9])\b", str(date_str))
        return int(match.group(1)) if match else None

    def _error_result(self, input_value: str, error: str) -> dict[str, Any]:
        return {
            "input": input_value,
            "found": False,
            "error": error,
            "historical_maps": [],
            "total_found": 0,
            "time_span": {"earliest": None, "latest": None},
            "manual_urls": {},
            "educational_note": _EDUCATIONAL_NOTE,
            "extracted_identifiers": [],
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
