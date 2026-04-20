"""Image metadata extractor using Pillow and standard library."""

from __future__ import annotations

import hashlib
import io
import mimetypes
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from PIL import ExifTags, Image


@dataclass
class GPSData:
    latitude: float
    longitude: float
    altitude: float | None = None
    gps_timestamp: str | None = None
    maps_url: str = field(init=False)

    def __post_init__(self) -> None:
        self.maps_url = f"https://maps.google.com/maps?q={self.latitude},{self.longitude}"


@dataclass
class ExtractedMetadata:
    filename: str
    file_hash: str
    file_size: int
    mime_type: str
    width: int | None = None
    height: int | None = None
    format: str | None = None
    camera_make: str | None = None
    camera_model: str | None = None
    taken_at: datetime | None = None
    gps: GPSData | None = None
    all_tags: dict[str, Any] = field(default_factory=dict)


# Mapping from numeric EXIF tag IDs to human-readable names
_EXIF_TAG_NAMES: dict[int, str] = {v: k for k, v in ExifTags.TAGS.items()}

# GPS IFD tag number within EXIF
_GPS_INFO_TAG = 34853


class ImageMetadataExtractor:
    """Extract EXIF and image metadata from raw file bytes."""

    def extract(self, file_bytes: bytes, filename: str) -> ExtractedMetadata:
        """Extract full metadata from image bytes.

        Returns an ExtractedMetadata instance. If the file has no EXIF data or
        an error occurs during EXIF parsing, all optional fields are None and
        all_tags will be empty.
        """
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        file_size = len(file_bytes)
        mime_type = self._detect_mime_type(file_bytes, filename)

        try:
            img = Image.open(io.BytesIO(file_bytes))
        except Exception:
            return ExtractedMetadata(
                filename=filename,
                file_hash=file_hash,
                file_size=file_size,
                mime_type=mime_type,
            )

        width, height = img.size
        fmt = img.format

        all_tags: dict[str, Any] = {}
        camera_make: str | None = None
        camera_model: str | None = None
        taken_at: datetime | None = None
        gps: GPSData | None = None

        try:
            raw_exif = img._getexif()  # type: ignore[attr-defined]
            if raw_exif:
                for tag_id, value in raw_exif.items():
                    tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                    if tag_id == _GPS_INFO_TAG:
                        # Don't store raw GPS IFD structure in all_tags; parse separately
                        gps = self._parse_gps(value)
                        if gps is not None:
                            all_tags["GPSInfo"] = {
                                "latitude": gps.latitude,
                                "longitude": gps.longitude,
                                "altitude": gps.altitude,
                                "gps_timestamp": gps.gps_timestamp,
                                "maps_url": gps.maps_url,
                            }
                    else:
                        serialised = self._serialise_value(value)
                        all_tags[tag_name] = serialised

                camera_make = self._get_str_tag(raw_exif, "Make")
                camera_model = self._get_str_tag(raw_exif, "Model")
                taken_at = self._parse_datetime(raw_exif)
        except (AttributeError, Exception):
            # Gracefully handle images without EXIF or unsupported formats
            pass

        return ExtractedMetadata(
            filename=filename,
            file_hash=file_hash,
            file_size=file_size,
            mime_type=mime_type,
            width=width,
            height=height,
            format=fmt,
            camera_make=camera_make,
            camera_model=camera_model,
            taken_at=taken_at,
            gps=gps,
            all_tags=all_tags,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _detect_mime_type(self, file_bytes: bytes, filename: str) -> str:
        """Detect MIME type from file magic bytes, falling back to filename extension."""
        magic_map: list[tuple[bytes, str]] = [
            (b"\xff\xd8\xff", "image/jpeg"),
            (b"\x89PNG\r\n\x1a\n", "image/png"),
            (b"GIF87a", "image/gif"),
            (b"GIF89a", "image/gif"),
            (b"RIFF", "image/webp"),  # confirmed below
            (b"BM", "image/bmp"),
        ]
        for magic, mime in magic_map:
            if file_bytes[: len(magic)].startswith(magic):
                # Extra check for WebP: RIFF????WEBP
                if mime == "image/webp" and len(file_bytes) >= 12:
                    if file_bytes[8:12] != b"WEBP":
                        continue
                return mime

        # TIFF: little-endian II or big-endian MM + magic 42
        if file_bytes[:4] in (b"II\x2a\x00", b"MM\x00\x2a"):
            return "image/tiff"

        # Fallback: guess from extension
        guessed, _ = mimetypes.guess_type(filename)
        return guessed or "application/octet-stream"

    def _get_str_tag(self, raw_exif: dict[int, Any], tag_name: str) -> str | None:
        """Retrieve a string EXIF tag by name, returning None if absent."""
        tag_id = _EXIF_TAG_NAMES.get(tag_name)
        if tag_id is None:
            return None
        value = raw_exif.get(tag_id)
        if value is None:
            return None
        return str(value).strip() or None

    def _parse_datetime(self, raw_exif: dict[int, Any]) -> datetime | None:
        """Parse DateTimeOriginal (tag 36867) from EXIF, falling back to DateTime (tag 306)."""
        for tag_name in ("DateTimeOriginal", "DateTime"):
            tag_id = _EXIF_TAG_NAMES.get(tag_name)
            if tag_id is None:
                continue
            value = raw_exif.get(tag_id)
            if not value:
                continue
            try:
                # EXIF datetime format: "YYYY:MM:DD HH:MM:SS"
                return datetime.strptime(str(value), "%Y:%m:%d %H:%M:%S")
            except ValueError:
                continue
        return None

    def _parse_gps(self, gps_info: dict[int, Any]) -> GPSData | None:
        """Convert raw EXIF GPS IFD dict to a GPSData instance.

        EXIF GPS tag IDs:
          1 = GPSLatitudeRef  (N/S)
          2 = GPSLatitude     (degrees, minutes, seconds as Fraction/IFDRational)
          3 = GPSLongitudeRef (E/W)
          4 = GPSLongitude
          5 = GPSAltitudeRef  (0 = above sea level, 1 = below)
          6 = GPSAltitude
          7 = GPSTimeStamp    (HH, MM, SS as Fraction)
        """
        if not gps_info:
            return None

        try:
            lat_ref: str | None = gps_info.get(1)
            lat_dms = gps_info.get(2)
            lon_ref: str | None = gps_info.get(3)
            lon_dms = gps_info.get(4)

            if not (lat_ref and lat_dms and lon_ref and lon_dms):
                return None

            latitude = self._dms_to_decimal(lat_dms, lat_ref)
            longitude = self._dms_to_decimal(lon_dms, lon_ref)

            # Altitude (optional)
            altitude: float | None = None
            alt_raw = gps_info.get(6)
            if alt_raw is not None:
                alt_ref = gps_info.get(5, 0)
                altitude = float(alt_raw)
                if alt_ref == 1:
                    altitude = -altitude

            # GPS timestamp (optional)
            gps_timestamp: str | None = None
            ts_raw = gps_info.get(7)
            if ts_raw is not None:
                try:
                    h, m, s = (float(x) for x in ts_raw)
                    gps_timestamp = f"{int(h):02d}:{int(m):02d}:{s:06.3f}"
                except (TypeError, ValueError):
                    pass

            return GPSData(
                latitude=latitude,
                longitude=longitude,
                altitude=altitude,
                gps_timestamp=gps_timestamp,
            )
        except Exception:
            return None

    @staticmethod
    def _dms_to_decimal(dms: tuple[Any, Any, Any], ref: str) -> float:
        """Convert degrees/minutes/seconds tuple to signed decimal degrees."""
        d = float(dms[0])
        m = float(dms[1])
        s = float(dms[2])
        decimal = d + m / 60.0 + s / 3600.0
        if ref in ("S", "W"):
            decimal = -decimal
        return round(decimal, 7)

    @staticmethod
    def _serialise_value(value: Any) -> Any:
        """Convert EXIF values to JSON-safe types."""
        if isinstance(value, bytes):
            # Represent binary blobs as hex string
            return value.hex()
        if isinstance(value, tuple):
            return [ImageMetadataExtractor._serialise_value(v) for v in value]
        try:
            # IFDRational and Fraction both support __float__
            return float(value)
        except (TypeError, ValueError):
            pass
        return str(value)
