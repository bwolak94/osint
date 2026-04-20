"""Metadata Scanner — EXIF from images and document metadata from PDFs.

OPSEC intelligence value:
  - EXIF GPS coordinates reveal the physical location where an image was taken.
  - Creator/Software fields expose internal tools and OS versions.
  - PDF metadata commonly contains: author usernames, internal network paths
    (UNC paths like \\\\server\\share), Windows SIDs, AD domain names.
  - Timestamps correlate operational activity to time zones.

Input entities:  URL (pointing to JPEG/PNG/TIFF/WebP or PDF)
Output entities:
  - PERSON       — author, artist, copyright fields
  - LOCATION     — GPS coordinates parsed to decimal degrees
  - INTERNAL_PATH — extracted filesystem/UNC paths
  - USERNAME     — extracted from internal paths (C:\\Users\\<name>)
"""

from __future__ import annotations

import io
import re
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_IMAGE_CONTENT_TYPES = ("image/jpeg", "image/jpg", "image/tiff", "image/png", "image/webp")
_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".tif", ".tiff", ".png", ".webp", ".heic")
_PDF_CONTENT_TYPES = ("application/pdf",)
_PDF_EXTENSION = ".pdf"

# PDF fields known to leak sensitive data
_SENSITIVE_PDF_FIELDS = {
    "Author", "Creator", "Producer", "ModDate", "CreationDate",
    "Subject", "Keywords", "Company", "Manager", "Title",
}

_MAX_DOWNLOAD_BYTES = 15 * 1024 * 1024  # 15 MB

# Patterns that reveal internal infrastructure in metadata values
_WIN_PATH_RE = re.compile(r"[A-Z]:\\[^\s'\"<>|*?]{4,}", re.IGNORECASE)
_UNC_PATH_RE = re.compile(r"\\\\[a-zA-Z0-9._-]+\\[^\s'\"<>|*?]{2,}", re.IGNORECASE)
_UNIX_HOME_RE = re.compile(r"/(?:home|Users)/([a-zA-Z0-9._-]+)", re.IGNORECASE)
_WIN_USER_RE = re.compile(r"[A-Z]:\\Users\\([a-zA-Z0-9._-]+)", re.IGNORECASE)


class MetadataScanner(BaseOsintScanner):
    """Extract forensic metadata from image URLs (EXIF) and PDF files.

    Input:  ScanInputType.URL — must resolve to an image or PDF.
    Output: person:, gps:, path:, username: identifiers.

    Optional Python dependencies (graceful fallback if missing):
      - Pillow >= 10.0  (pip install Pillow)  — image EXIF
      - pypdf >= 4.0    (pip install pypdf)   — PDF metadata
    """

    scanner_name = "metadata_extractor"
    supported_input_types = frozenset({ScanInputType.URL})
    cache_ttl = 86400  # 24 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        url = input_value

        content_type, raw_bytes = await self._fetch_content(url)
        if not raw_bytes:
            return {
                "url": url,
                "found": False,
                "error": "Failed to download content",
                "extracted_identifiers": [],
            }

        if self._is_image(url, content_type):
            return self._process_image(url, raw_bytes)
        if self._is_pdf(url, content_type):
            return self._process_pdf(url, raw_bytes)

        return {
            "url": url,
            "found": False,
            "error": f"Unsupported content type: {content_type!r}. Supported: image/*, application/pdf",
            "content_type": content_type,
            "extracted_identifiers": [],
        }

    # ------------------------------------------------------------------
    # Fetch
    # ------------------------------------------------------------------

    async def _fetch_content(self, url: str) -> tuple[str, bytes]:
        """Stream-download the resource, capping at _MAX_DOWNLOAD_BYTES."""
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; MetadataScanner/1.0)"},
            ) as client:
                async with client.stream("GET", url) as resp:
                    resp.raise_for_status()
                    content_type = resp.headers.get("content-type", "").lower()
                    chunks: list[bytes] = []
                    total = 0
                    async for chunk in resp.aiter_bytes(chunk_size=65_536):
                        chunks.append(chunk)
                        total += len(chunk)
                        if total >= _MAX_DOWNLOAD_BYTES:
                            log.warning("Download cap reached", url=url, bytes=total)
                            break
                    return content_type, b"".join(chunks)
        except httpx.HTTPStatusError as exc:
            log.warning("Metadata fetch HTTP error", url=url, status=exc.response.status_code)
            return "", b""
        except Exception as exc:
            log.error("Metadata fetch failed", url=url, error=str(exc))
            return "", b""

    # ------------------------------------------------------------------
    # Type detection
    # ------------------------------------------------------------------

    def _is_image(self, url: str, content_type: str) -> bool:
        ext = urlparse(url).path.lower()
        return (
            any(ct in content_type for ct in _IMAGE_CONTENT_TYPES)
            or any(ext.endswith(e) for e in _IMAGE_EXTENSIONS)
        )

    def _is_pdf(self, url: str, content_type: str) -> bool:
        ext = urlparse(url).path.lower()
        return any(ct in content_type for ct in _PDF_CONTENT_TYPES) or ext.endswith(_PDF_EXTENSION)

    # ------------------------------------------------------------------
    # Image EXIF
    # ------------------------------------------------------------------

    def _process_image(self, url: str, data: bytes) -> dict[str, Any]:
        try:
            from PIL import Image
            from PIL.ExifTags import GPSTAGS, TAGS
        except ImportError:
            return {
                "url": url,
                "found": False,
                "error": "Pillow not installed. Run: pip install Pillow",
                "extracted_identifiers": [],
            }

        try:
            img = Image.open(io.BytesIO(data))
            exif_raw: dict[int, Any] | None = img._getexif()  # type: ignore[attr-defined]
        except Exception as exc:
            return {"url": url, "found": False, "error": f"EXIF parse error: {exc}", "extracted_identifiers": []}

        if not exif_raw:
            return {
                "url": url,
                "found": True,
                "has_exif": False,
                "image_format": img.format,
                "image_size": list(img.size),
                "message": "No EXIF data embedded in image",
                "extracted_identifiers": [],
            }

        exif_decoded: dict[str, Any] = {}
        gps_raw: dict[str, Any] = {}
        GPS_TAG_ID = 34853

        for tag_id, value in exif_raw.items():
            tag_name = TAGS.get(tag_id, str(tag_id))
            if tag_id == GPS_TAG_ID and isinstance(value, dict):
                for gps_tag_id, gps_val in value.items():
                    gps_name = GPSTAGS.get(gps_tag_id, str(gps_tag_id))
                    gps_raw[gps_name] = str(gps_val)
            else:
                # Sanitise non-serialisable types
                if isinstance(value, (bytes, bytearray)):
                    value = value.hex()
                exif_decoded[tag_name] = str(value) if not isinstance(value, (str, int, float, bool)) else value

        gps_coords = self._parse_gps(gps_raw)
        identifiers: list[str] = []

        if gps_coords:
            identifiers.append(f"gps:{gps_coords['lat']},{gps_coords['lon']}")

        for field_name in ("Artist", "Copyright", "Author", "XPAuthor"):
            value_str = str(exif_decoded.get(field_name, "")).strip("\x00").strip()
            if value_str:
                identifiers.append(f"person:{value_str}")

        software = str(exif_decoded.get("Software", "")).strip()
        if software:
            identifiers.append(f"software:{software}")

        camera_make = exif_decoded.get("Make", "")
        camera_model = exif_decoded.get("Model", "")

        return {
            "url": url,
            "found": True,
            "has_exif": True,
            "image_format": img.format,
            "image_size": list(img.size),
            "exif": exif_decoded,
            "gps_raw": gps_raw,
            "gps_coordinates": gps_coords,
            "camera_make": camera_make,
            "camera_model": camera_model,
            "extracted_identifiers": identifiers,
        }

    def _parse_gps(self, gps_data: dict[str, Any]) -> dict[str, float] | None:
        """Convert EXIF GPS rational tuples to decimal-degree floats."""
        def _rational_to_float(s: str, ref: str) -> float:
            nums = re.findall(r"[\d.]+", s)
            if len(nums) < 6:
                return 0.0
            # Each coordinate component is a (numerator, denominator) pair
            d = float(nums[0]) / (float(nums[1]) or 1)
            m = float(nums[2]) / (float(nums[3]) or 1)
            sec = float(nums[4]) / (float(nums[5]) or 1)
            decimal = d + m / 60 + sec / 3600
            return -decimal if ref in ("S", "W") else decimal

        try:
            lat_raw = gps_data.get("GPSLatitude", "")
            lat_ref = gps_data.get("GPSLatitudeRef", "N")
            lon_raw = gps_data.get("GPSLongitude", "")
            lon_ref = gps_data.get("GPSLongitudeRef", "E")

            if not lat_raw or not lon_raw:
                return None

            return {
                "lat": round(_rational_to_float(lat_raw, lat_ref), 6),
                "lon": round(_rational_to_float(lon_raw, lon_ref), 6),
            }
        except Exception:
            return None

    # ------------------------------------------------------------------
    # PDF metadata
    # ------------------------------------------------------------------

    def _process_pdf(self, url: str, data: bytes) -> dict[str, Any]:
        try:
            import pypdf
        except ImportError:
            return {
                "url": url,
                "found": False,
                "error": "pypdf not installed. Run: pip install pypdf",
                "extracted_identifiers": [],
            }

        try:
            reader = pypdf.PdfReader(io.BytesIO(data), strict=False)
            meta = reader.metadata or {}
        except Exception as exc:
            return {"url": url, "found": False, "error": f"PDF parse error: {exc}", "extracted_identifiers": []}

        # Normalise keys: strip leading "/"
        metadata: dict[str, str] = {
            str(k).lstrip("/"): str(v) if v is not None else ""
            for k, v in meta.items()
        }

        all_values_str = " ".join(metadata.values())

        # Extract Windows user paths (C:\Users\username)
        usernames: list[str] = list(dict.fromkeys(
            _WIN_USER_RE.findall(all_values_str)
            + _UNIX_HOME_RE.findall(all_values_str)
        ))

        # Extract filesystem/UNC paths
        win_paths = _WIN_PATH_RE.findall(all_values_str)
        unc_paths = _UNC_PATH_RE.findall(all_values_str)
        internal_paths = list(dict.fromkeys(win_paths + unc_paths))

        identifiers: list[str] = []
        for username in usernames:
            identifiers.append(f"username:{username}")
        for path in internal_paths:
            identifiers.append(f"path:{path}")

        author = metadata.get("Author", "").strip()
        if author:
            identifiers.append(f"person:{author}")

        creator = metadata.get("Creator", "").strip()
        if creator:
            identifiers.append(f"software:{creator}")

        return {
            "url": url,
            "found": True,
            "page_count": len(reader.pages),
            "metadata": metadata,
            "sensitive_fields": {k: v for k, v in metadata.items() if k in _SENSITIVE_PDF_FIELDS},
            "discovered_usernames": usernames,
            "internal_paths": internal_paths,
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
