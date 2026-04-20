"""Webcam Finder — discovers publicly accessible webcams and IP cameras near given coordinates."""
import os
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_SHODAN_SEARCH_URL = "https://api.shodan.io/shodan/host/search"
_SHODAN_INTERNETDB_URL = "https://internetdb.shodan.io"

# Common webcam-related Shodan queries
_WEBCAM_QUERIES = [
    'webcam has_screenshot:true',
    'product:"IP Camera" has_screenshot:true',
    '"Network Camera" has_screenshot:true',
    '"Axis" has_screenshot:true',
    '"Hikvision" has_screenshot:true',
]


def _parse_coordinates(value: str) -> tuple[float, float]:
    parts = value.strip().split(",")
    if len(parts) < 2:
        raise ValueError(f"Expected 'lat,lon' format, got: {value!r}")
    return float(parts[0].strip()), float(parts[1].strip())


def _build_geo_filter(lat: float, lon: float, radius_km: float = 10.0) -> str:
    """Build a Shodan geo: filter string."""
    return f"geo:{lat},{lon},{radius_km}"


class WebcamFinderScanner(BaseOsintScanner):
    """Discovers publicly accessible IP cameras near coordinates using Shodan API or manual fallback guidance."""

    scanner_name = "webcam_finder"
    supported_input_types = frozenset({ScanInputType.COORDINATES})
    cache_ttl = 3600

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        try:
            lat, lon = _parse_coordinates(input_value)
        except ValueError as exc:
            return {"found": False, "error": str(exc)}

        api_key = os.getenv("SHODAN_API_KEY")

        cameras: list[dict[str, Any]] = []
        api_used = "none"
        error_msg: str | None = None

        if api_key:
            geo_filter = _build_geo_filter(lat, lon, radius_km=10.0)
            query = f"has_screenshot:true {geo_filter}"

            try:
                async with httpx.AsyncClient(timeout=20) as client:
                    resp = await client.get(
                        _SHODAN_SEARCH_URL,
                        params={
                            "key": api_key,
                            "query": query,
                            "facets": "port,country",
                            "page": 1,
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()

                for match in data.get("matches", [])[:20]:
                    location = match.get("location", {})
                    cameras.append({
                        "ip": match.get("ip_str"),
                        "port": match.get("port"),
                        "hostnames": match.get("hostnames", []),
                        "org": match.get("org"),
                        "isp": match.get("isp"),
                        "product": match.get("product"),
                        "version": match.get("version"),
                        "country": location.get("country_name"),
                        "city": location.get("city"),
                        "coordinates": {
                            "latitude": location.get("latitude"),
                            "longitude": location.get("longitude"),
                        },
                        "has_screenshot": True,
                        "screenshot_url": f"https://www.shodan.io/host/{match.get('ip_str')}",
                        "last_seen": match.get("timestamp"),
                        "vulnerability_count": len(match.get("vulns", {})),
                    })

                api_used = "shodan_search"
                log.info("webcam_finder: Shodan search completed", count=len(cameras))

            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 401:
                    error_msg = "Shodan API key invalid or insufficient permissions"
                else:
                    error_msg = f"Shodan API error {exc.response.status_code}"
                log.warning("webcam_finder: Shodan request failed", error=error_msg)
            except Exception as exc:
                error_msg = f"Shodan request failed: {exc}"
                log.warning("webcam_finder: Shodan request failed", error=str(exc))

        # Fallback: query Shodan InternetDB for nearby IPs (free, no key needed)
        # InternetDB only accepts IPs, so we provide guidance instead
        if not cameras:
            api_used = "none"

        # Build manual search links regardless
        search_links: list[dict[str, str]] = [
            {
                "service": "Shodan Maps",
                "url": f"https://maps.shodan.io/#/{lat}/{lon}/14/basic",
                "description": "Interactive map of internet-connected devices near these coordinates",
            },
            {
                "service": "Shodan Search (webcams)",
                "url": f"https://www.shodan.io/search?query=has_screenshot%3Atrue+geo%3A{lat}%2C{lon}%2C10",
                "description": "Shodan search for devices with screenshots near coordinates",
            },
            {
                "service": "Insecam",
                "url": f"http://www.insecam.org/en/bycountry/",
                "description": "Directory of publicly accessible cameras (browse by country)",
            },
            {
                "service": "EarthCam",
                "url": f"https://www.earthcam.com/",
                "description": "Network of public webcams worldwide with map search",
            },
            {
                "service": "Windy Webcams",
                "url": f"https://www.windy.com/webcams/{lat}/{lon}/14",
                "description": "Weather and landscape webcams near these coordinates",
            },
        ]

        return {
            "found": bool(cameras),
            "coordinates": {"latitude": lat, "longitude": lon},
            "search_radius_km": 10,
            "camera_count": len(cameras),
            "cameras": cameras,
            "api_used": api_used,
            "error": error_msg,
            "manual_search_links": search_links,
            "requires_api_key": not bool(api_key),
            "educational_note": (
                "Shodan indexes internet-connected devices including IP cameras, NVRs, and DVRs. "
                "Many are left with default credentials (admin/admin, admin/12345). "
                "Accessing cameras without authorization is illegal — use only for authorized investigations. "
                "Set SHODAN_API_KEY environment variable for full search capabilities."
            ),
        }
