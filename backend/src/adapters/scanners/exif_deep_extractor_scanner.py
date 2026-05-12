"""EXIF Deep Extractor — downloads an image and extracts full EXIF metadata including GPS."""
import io
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_INTERESTING_TAGS = {
    "GPSInfo", "Make", "Model", "DateTime", "DateTimeOriginal",
    "Orientation", "Flash", "FocalLength", "ExifImageWidth",
    "ExifImageHeight", "Software", "Artist", "Copyright",
    "XResolution", "YResolution", "LensModel", "ISOSpeedRatings",
    "ExposureTime", "FNumber", "WhiteBalance", "SceneCaptureType",
}

_GPS_IFD_TAG = 34853  # ExifTags.TAGS reverse for GPSInfo


def _dms_to_decimal(dms: tuple, ref: str) -> float:
    """Convert degrees/minutes/seconds tuple to decimal degrees."""
    d, m, s = dms
    decimal = float(d) + float(m) / 60 + float(s) / 3600
    if ref in ("S", "W"):
        decimal = -decimal
    return round(decimal, 7)


class ExifDeepExtractorScanner(BaseOsintScanner):
    """Downloads an image URL and extracts full EXIF metadata including hidden GPS coordinates."""

    scanner_name = "exif_deep_extractor"
    supported_input_types = frozenset({ScanInputType.URL})
    cache_ttl = 86400

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        try:
            from PIL import Image
            from PIL.ExifTags import TAGS, GPSTAGS
        except ImportError:
            return {"found": False, "error": "Pillow not installed"}

        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(input_value, headers={"User-Agent": "Mozilla/5.0"})
                resp.raise_for_status()
                content_type = resp.headers.get("content-type", "")
                if "image" not in content_type:
                    return {
                        "found": False,
                        "error": f"URL does not point to an image (content-type: {content_type})",
                    }
                image_bytes = resp.content
        except Exception as exc:
            return {"found": False, "error": f"Failed to fetch image: {exc}"}

        try:
            img = Image.open(io.BytesIO(image_bytes))
            raw_exif = img._getexif() or {}  # type: ignore[attr-defined]
        except Exception as exc:
            return {"found": False, "error": f"Failed to parse image: {exc}"}

        if not raw_exif:
            return {
                "found": False,
                "image_format": img.format,
                "image_size": list(img.size),
                "note": "No EXIF metadata found. Image may have been stripped.",
            }

        tags: dict[str, Any] = {}
        gps_info: dict[str, Any] = {}

        for tag_id, value in raw_exif.items():
            tag_name = TAGS.get(tag_id, str(tag_id))
            if tag_name == "GPSInfo" and isinstance(value, dict):
                for gps_tag_id, gps_val in value.items():
                    gps_tag_name = GPSTAGS.get(gps_tag_id, str(gps_tag_id))
                    gps_info[gps_tag_name] = str(gps_val)
            elif tag_name in _INTERESTING_TAGS:
                tags[tag_name] = str(value)[:200]

        # Attempt to parse GPS coordinates
        coordinates: dict[str, float] | None = None
        try:
            if "GPSLatitude" in gps_info and "GPSLongitude" in gps_info:
                lat_raw = raw_exif.get(34853, {})
                if isinstance(lat_raw, dict):
                    lat = _dms_to_decimal(
                        lat_raw.get(2, (0, 0, 0)),
                        lat_raw.get(1, "N"),
                    )
                    lon = _dms_to_decimal(
                        lat_raw.get(4, (0, 0, 0)),
                        lat_raw.get(3, "E"),
                    )
                    coordinates = {"latitude": lat, "longitude": lon}
        except Exception:
            pass

        extracted_identifiers = []
        if coordinates:
            extracted_identifiers.append(
                f"coordinates:{coordinates['latitude']},{coordinates['longitude']}"
            )

        return {
            "found": bool(tags or gps_info),
            "image_url": input_value,
            "image_format": img.format,
            "image_size": list(img.size),
            "exif_tags": tags,
            "gps_info": gps_info,
            "coordinates": coordinates,
            "extracted_identifiers": extracted_identifiers,
            "educational_note": (
                "EXIF metadata is embedded in images by cameras and smartphones. "
                "GPS coordinates reveal exact capture location. Always strip EXIF before sharing sensitive images."
            ),
        }
