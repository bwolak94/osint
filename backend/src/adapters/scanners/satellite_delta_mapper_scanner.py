"""Satellite Delta Mapper — compares satellite imagery across two dates for change detection."""
import httpx
from typing import Any

import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()


def _parse_coordinates(value: str) -> tuple[float, float]:
    parts = value.strip().split(",")
    if len(parts) != 2:
        raise ValueError(f"Expected 'lat,lon' format, got: {value!r}")
    return float(parts[0].strip()), float(parts[1].strip())


class SatelliteDeltaMapperScanner(BaseOsintScanner):
    """Queries Copernicus catalogue for available Sentinel-2 imagery and returns tile URLs for change detection."""

    scanner_name = "satellite_delta_mapper"
    supported_input_types = frozenset({ScanInputType.COORDINATES})
    cache_ttl = 3600

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        try:
            lat, lon = _parse_coordinates(input_value)
        except ValueError as exc:
            return {"found": False, "error": str(exc)}

        delta = 0.05  # ~5 km bounding box
        bbox = {
            "west": round(lon - delta, 6),
            "south": round(lat - delta, 6),
            "east": round(lon + delta, 6),
            "north": round(lat + delta, 6),
        }

        # Query Copernicus Open Access Hub for recent Sentinel-2 scenes
        catalogue_url = (
            "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
            f"?$filter=Collection/Name eq 'SENTINEL-2' and "
            f"OData.CSC.Intersects(area=geography'SRID=4326;POLYGON(("
            f"{bbox['west']} {bbox['south']},"
            f"{bbox['east']} {bbox['south']},"
            f"{bbox['east']} {bbox['north']},"
            f"{bbox['west']} {bbox['north']},"
            f"{bbox['west']} {bbox['south']}"
            f"))')&$orderby=ContentDate/Start desc&$top=5&$expand=Attributes"
        )

        scenes: list[dict[str, Any]] = []
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(catalogue_url)
                if resp.status_code == 200:
                    data = resp.json()
                    for product in data.get("value", [])[:5]:
                        scenes.append({
                            "id": product.get("Id"),
                            "name": product.get("Name"),
                            "date": product.get("ContentDate", {}).get("Start"),
                            "cloud_cover": next(
                                (
                                    a.get("Value")
                                    for a in product.get("Attributes", {}).get("results", [])
                                    if a.get("Name") == "cloudCover"
                                ),
                                None,
                            ),
                        })
        except Exception as exc:
            log.warning("satellite_delta_mapper: catalogue query failed", error=str(exc))

        # Build OpenStreetMap tile URL (always available, no auth)
        zoom = 14
        osm_tile_url = f"https://tile.openstreetmap.org/{zoom}/{lat}/{lon}.png"

        # Sentinel Hub EO Browser URL for user to open manually
        eo_browser_url = (
            f"https://apps.sentinel-hub.com/eo-browser/"
            f"?lat={lat}&lng={lon}&zoom=13&themeId=DEFAULT-THEME&datasetId=S2L2A"
        )

        return {
            "found": True,
            "coordinates": {"latitude": lat, "longitude": lon},
            "bounding_box": bbox,
            "recent_sentinel2_scenes": scenes,
            "scene_count": len(scenes),
            "eo_browser_url": eo_browser_url,
            "osm_tile_url": osm_tile_url,
            "educational_note": (
                "Sentinel-2 provides free 10m-resolution multispectral imagery every 5 days. "
                "Comparing two dates reveals construction, deforestation, flooding, or military activity."
            ),
        }
