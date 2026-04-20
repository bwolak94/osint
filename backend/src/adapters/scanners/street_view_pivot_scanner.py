"""Street View Pivot Scanner — multi-provider street-level imagery aggregator.

OPSEC intelligence value:
  - Street-level imagery is essential for confirming physical location of a target facility,
    building entrance, vehicle, or individual observed in open-source photos.
  - Cross-referencing Google Street View capture dates with Mapillary crowdsourced images
    creates a historical timeline of changes at a location.
  - Bing Streetside and Apple Look Around provide independent image sources useful when
    Google Street View is outdated or absent in certain regions.
  - Mapillary images include camera direction (bearing) useful for perspective matching.

Input entities:  COORDINATES — "lat,lon" decimal string
Output entities:
  - street_view_urls    — provider-keyed dict of direct viewer links
  - mapillary_images    — list of nearby crowdsourced image metadata
  - coverage_available  — bool: at least one provider has imagery nearby
  - educational_note    — methodology for street-level pivot in OSINT workflow
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlencode

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_GOOGLE_STREETVIEW_METADATA_URL = "https://maps.googleapis.com/maps/api/streetview/metadata"
_MAPILLARY_IMAGES_URL = "https://graph.mapillary.com/images"
_HEADERS = {"User-Agent": "OSINT-Platform/1.0 contact@example.com"}

_EDUCATIONAL_NOTE = (
    "Street-level imagery pivot workflow: "
    "1) Confirm target coordinates using Nominatim or GeoIP. "
    "2) Load Google Street View to identify building facades, signage, and vehicle plates. "
    "3) Check capture date — older imagery may not reflect current state. "
    "4) Cross-reference with Mapillary for crowdsourced/recent contributions. "
    "5) Use Bing Streetside for alternative viewpoints (different capture angle/date). "
    "6) Apple Look Around provides high-resolution 3D imagery in supported cities. "
    "7) Compare shadow direction/length across providers to estimate time-of-day of capture."
)


def _build_google_maps_sv_url(lat: float, lon: float) -> str:
    """Direct Google Maps Street View URL (no API key required)."""
    return f"https://www.google.com/maps/@{lat},{lon},3a,75y,0h,90t/data=!3m6!1e1"


def _build_apple_look_around_url(lat: float, lon: float) -> str:
    """Apple Maps Look Around deep-link URL."""
    return f"https://maps.apple.com/?ll={lat},{lon}&t=k&z=17"


def _build_bing_streetside_url(lat: float, lon: float) -> str:
    """Bing Maps Bird's Eye / Streetside URL."""
    return f"https://www.bing.com/maps?cp={lat}~{lon}&lvl=17&style=x&dir=0"


def _build_yandex_panorama_url(lat: float, lon: float) -> str:
    """Yandex Panorama (Panorama) URL — good coverage in Russia/CIS."""
    return f"https://yandex.com/maps/?ll={lon},{lat}&z=16&l=stv&panorama[point]={lon},{lat}"


def _build_kakao_roadview_url(lat: float, lon: float) -> str:
    """Kakao Maps Road View (South Korea)."""
    return f"https://map.kakao.com/?map_type=TYPE_ROADVIEW&q={lat},{lon}"


class StreetViewPivotScanner(BaseOsintScanner):
    """Aggregate street-level imagery links and Mapillary metadata for a coordinate pair.

    Input:  ScanInputType.COORDINATES — "lat,lon" string.
    Output: street_view_urls dict, mapillary_images list, coverage_available bool.

    Optional environment variables:
      - GOOGLE_MAPS_API_KEY — enables Google Street View metadata check
      - MAPILLARY_TOKEN     — Mapillary Graph API access token for image search
    """

    scanner_name = "street_view_pivot"
    supported_input_types = frozenset({ScanInputType.COORDINATES})
    cache_ttl = 86400

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        lat, lon = self._parse_coordinates(input_value)
        if lat is None or lon is None:
            return self._error_result(input_value, "Invalid coordinate format. Expected 'lat,lon'.")

        google_api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        mapillary_token = os.getenv("MAPILLARY_TOKEN")

        # Build static deep-link URLs (no auth required)
        street_view_urls: dict[str, str] = {
            "google_street_view": _build_google_maps_sv_url(lat, lon),
            "apple_look_around": _build_apple_look_around_url(lat, lon),
            "bing_streetside": _build_bing_streetside_url(lat, lon),
            "yandex_panorama": _build_yandex_panorama_url(lat, lon),
            "kakao_roadview": _build_kakao_roadview_url(lat, lon),
        }

        google_metadata: dict[str, Any] = {}
        mapillary_images: list[dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=20.0, headers=_HEADERS) as client:
            # Optional: Google Street View metadata (requires API key)
            if google_api_key:
                google_metadata = await self._fetch_google_metadata(client, lat, lon, google_api_key)

            # Optional: Mapillary image search (token enhances rate limit)
            mapillary_images = await self._fetch_mapillary_images(client, lat, lon, mapillary_token)

        google_sv_available = google_metadata.get("status") == "OK"
        mapillary_available = len(mapillary_images) > 0
        coverage_available = google_sv_available or mapillary_available

        return {
            "input": input_value,
            "found": True,
            "lat": lat,
            "lon": lon,
            "street_view_urls": street_view_urls,
            "google_street_view_metadata": google_metadata,
            "google_street_view_available": google_sv_available,
            "mapillary_images": mapillary_images,
            "mapillary_count": len(mapillary_images),
            "coverage_available": coverage_available,
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
    # Google Street View Metadata
    # ------------------------------------------------------------------

    async def _fetch_google_metadata(
        self, client: httpx.AsyncClient, lat: float, lon: float, api_key: str
    ) -> dict[str, Any]:
        """Fetch Street View metadata without consuming image quota."""
        try:
            params = {
                "location": f"{lat},{lon}",
                "radius": "50",
                "key": api_key,
            }
            resp = await client.get(_GOOGLE_STREETVIEW_METADATA_URL, params=params)
            if resp.status_code != 200:
                log.warning("Google SV metadata error", status=resp.status_code)
                return {}
            data = resp.json()
            return {
                "status": data.get("status"),
                "pano_id": data.get("pano_id"),
                "location": data.get("location", {}),
                "date": data.get("date"),
                "copyright": data.get("copyright"),
            }
        except Exception as exc:
            log.warning("Google Street View metadata fetch failed", lat=lat, lon=lon, error=str(exc))
            return {}

    # ------------------------------------------------------------------
    # Mapillary
    # ------------------------------------------------------------------

    async def _fetch_mapillary_images(
        self, client: httpx.AsyncClient, lat: float, lon: float, token: str | None
    ) -> list[dict[str, Any]]:
        """Search Mapillary Graph API for nearby images."""
        headers: dict[str, str] = {}
        if token:
            headers["Authorization"] = f"OAuth {token}"

        params = {
            "fields": "id,thumb_256_url,captured_at,compass_angle,geometry",
            "bbox": f"{lon - 0.001},{lat - 0.001},{lon + 0.001},{lat + 0.001}",
            "limit": "20",
        }
        try:
            resp = await client.get(_MAPILLARY_IMAGES_URL, params=params, headers=headers)
            if resp.status_code not in (200, 201):
                log.warning("Mapillary API error", status=resp.status_code)
                return []
            data = resp.json()
            images = []
            for img in data.get("data", []):
                geom = img.get("geometry", {})
                coords = geom.get("coordinates", [None, None])
                images.append({
                    "id": img.get("id"),
                    "thumb_url": img.get("thumb_256_url"),
                    "captured_at": img.get("captured_at"),
                    "bearing_degrees": img.get("compass_angle"),
                    "lon": coords[0] if coords else None,
                    "lat": coords[1] if coords else None,
                    "mapillary_viewer_url": f"https://www.mapillary.com/app/?pKey={img.get('id')}",
                })
            return images
        except Exception as exc:
            log.warning("Mapillary image fetch failed", lat=lat, lon=lon, error=str(exc))
            return []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _error_result(self, input_value: str, error: str) -> dict[str, Any]:
        return {
            "input": input_value,
            "found": False,
            "error": error,
            "street_view_urls": {},
            "google_street_view_metadata": {},
            "google_street_view_available": False,
            "mapillary_images": [],
            "mapillary_count": 0,
            "coverage_available": False,
            "educational_note": _EDUCATIONAL_NOTE,
            "extracted_identifiers": [],
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
