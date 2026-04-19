"""ExifTool-enhanced scanner — deep EXIF/metadata extraction with GPS reverse geocoding."""

import asyncio
import hashlib
import io
import json
import os
import re
import tempfile
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024  # 20 MB
_INTERNAL_PATH_RE = re.compile(
    r"(?:\\\\[A-Za-z0-9._-]+\\[A-Za-z0-9._\-/\\]+|/(?:home|Users|var|opt|srv|mnt)/[^\s\"'<>]+)"
)
_USERNAME_RE = re.compile(r"(?:^|[/\\])([A-Za-z][A-Za-z0-9._-]{2,})[/\\]")


class ExifToolEnhancedScanner(BaseOsintScanner):
    scanner_name = "exiftool_enhanced"
    supported_input_types = frozenset({ScanInputType.URL})
    cache_ttl = 86400

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        url = input_value.strip()
        ext = self._guess_ext(url)

        content, size = await self._download_file(url)
        if not content:
            return {
                "url": url,
                "found": False,
                "error": "Download failed or empty",
                "extracted_identifiers": [],
            }

        file_hash = hashlib.sha256(content[:4096]).hexdigest()[:16]
        tmp_path = os.path.join(tempfile.gettempdir(), f"exiftool_{file_hash}.{ext}")
        try:
            with open(tmp_path, "wb") as fh:
                fh.write(content)

            all_metadata = await self._run_exiftool(tmp_path)
            if not all_metadata:
                all_metadata = self._fallback_extract(content, ext, tmp_path)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        gps = self._parse_gps(all_metadata)
        location_name = ""
        if gps.get("latitude") is not None and gps.get("longitude") is not None:
            location_name = await self._reverse_geocode(gps["latitude"], gps["longitude"])

        camera_info = self._extract_camera(all_metadata)
        author_info = self._extract_author(all_metadata)
        software = all_metadata.get("Software") or all_metadata.get("Creator") or ""
        sensitive = self._detect_sensitive(all_metadata, gps)

        identifiers: list[str] = []
        if gps.get("latitude") is not None:
            identifiers.append(f"gps:{gps['latitude']},{gps['longitude']}")
        if author_info.get("author"):
            identifiers.append(f"person:{author_info['author']}")
        for path in sensitive:
            m = re.search(r"\\\\([A-Za-z0-9._-]+)\\", path)
            if m:
                identifiers.append(f"domain:{m.group(1)}")

        return {
            "url": url,
            "file_size_bytes": size,
            "all_metadata": all_metadata,
            "gps_coordinates": gps,
            "location_name": location_name,
            "camera_info": camera_info,
            "author_info": author_info,
            "software": str(software),
            "sensitive_fields": sensitive,
            "extracted_identifiers": list(dict.fromkeys(identifiers)),
        }

    def _guess_ext(self, url: str) -> str:
        path = urlparse(url).path.lower()
        for ext in ("jpg", "jpeg", "png", "tiff", "tif", "heic", "pdf", "docx", "doc", "mp4", "mov"):
            if path.endswith(f".{ext}"):
                return ext
        return "bin"

    async def _download_file(self, url: str) -> tuple[bytes, int]:
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                async with client.stream("GET", url, headers={"User-Agent": "Mozilla/5.0"}) as resp:
                    if resp.status_code != 200:
                        return b"", 0
                    chunks: list[bytes] = []
                    total = 0
                    async for chunk in resp.aiter_bytes(65536):
                        chunks.append(chunk)
                        total += len(chunk)
                        if total >= _MAX_DOWNLOAD_BYTES:
                            break
                    return b"".join(chunks), total
        except Exception as exc:
            log.warning("ExifTool download failed", url=url, error=str(exc))
            return b"", 0

    async def _run_exiftool(self, path: str) -> dict[str, Any]:
        try:
            proc = await asyncio.create_subprocess_exec(
                "exiftool", "-json", "-n", "-gps:all", "-xmp:all", "-iptc:all", "-all", path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
            if proc.returncode == 0 and stdout:
                data = json.loads(stdout.decode("utf-8", errors="replace"))
                if isinstance(data, list) and data:
                    return data[0]
        except (FileNotFoundError, asyncio.TimeoutError, json.JSONDecodeError):
            pass
        except Exception as exc:
            log.debug("exiftool subprocess error", error=str(exc))
        return {}

    def _fallback_extract(self, content: bytes, ext: str, path: str) -> dict[str, Any]:
        meta: dict[str, Any] = {}
        if ext in {"jpg", "jpeg", "png", "tiff", "tif", "heic"}:
            try:
                from PIL import Image  # type: ignore[import-untyped]
                from PIL.ExifTags import TAGS  # type: ignore[import-untyped]

                img = Image.open(io.BytesIO(content))
                exif_data = img._getexif()  # type: ignore[attr-defined]
                if exif_data:
                    for tag_id, value in exif_data.items():
                        tag = TAGS.get(tag_id, str(tag_id))
                        meta[tag] = str(value)
            except ImportError:
                log.debug("Pillow not installed, skipping image EXIF")
            except Exception as exc:
                log.debug("Pillow EXIF extraction failed", error=str(exc))
        elif ext == "pdf":
            try:
                import pypdf  # type: ignore[import-untyped]

                reader = pypdf.PdfReader(io.BytesIO(content))
                pdf_meta = reader.metadata or {}
                for k, v in pdf_meta.items():
                    meta[k.lstrip("/")] = str(v)
            except ImportError:
                log.debug("pypdf not installed, skipping PDF metadata")
            except Exception as exc:
                log.debug("pypdf metadata extraction failed", error=str(exc))
        return meta

    def _parse_gps(self, meta: dict[str, Any]) -> dict[str, Any]:
        lat = meta.get("GPSLatitude") or meta.get("Latitude")
        lon = meta.get("GPSLongitude") or meta.get("Longitude")
        alt = meta.get("GPSAltitude") or meta.get("Altitude")
        if lat is None or lon is None:
            return {}
        try:
            return {
                "latitude": float(lat),
                "longitude": float(lon),
                "altitude": float(alt) if alt is not None else None,
            }
        except (TypeError, ValueError):
            return {}

    async def _reverse_geocode(self, lat: float, lon: float) -> str:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}"
        headers = {"User-Agent": "OSINT-Platform/1.0"}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("display_name", "")
        except Exception as exc:
            log.debug("Reverse geocode failed", error=str(exc))
        return ""

    def _extract_camera(self, meta: dict[str, Any]) -> dict[str, Any]:
        return {
            "make": meta.get("Make", ""),
            "model": meta.get("Model", ""),
            "serial": meta.get("SerialNumber", ""),
            "lens": meta.get("LensModel", ""),
        }

    def _extract_author(self, meta: dict[str, Any]) -> dict[str, Any]:
        author = (
            meta.get("Author")
            or meta.get("Creator")
            or meta.get("Artist")
            or meta.get("XMP:Creator")
            or ""
        )
        return {
            "author": str(author).strip() if author else "",
            "copyright": str(meta.get("Copyright", "")).strip(),
            "date_created": str(meta.get("DateTimeOriginal") or meta.get("CreateDate") or ""),
            "date_modified": str(meta.get("ModifyDate") or meta.get("FileModifyDate") or ""),
        }

    def _detect_sensitive(self, meta: dict[str, Any], gps: dict[str, Any]) -> list[str]:
        sensitive: list[str] = []
        if gps.get("latitude") is not None:
            sensitive.append(f"GPS coordinates: {gps['latitude']},{gps['longitude']}")
        for key, value in meta.items():
            value_str = str(value)
            paths = _INTERNAL_PATH_RE.findall(value_str)
            for p in paths:
                sensitive.append(f"Internal path in {key}: {p}")
            if re.search(r"\d+\.\d+\.\d+", value_str) and key in {"Software", "Creator", "Producer"}:
                sensitive.append(f"Software version in {key}: {value_str}")
            users = _USERNAME_RE.findall(value_str)
            for u in users:
                if len(u) > 3:
                    sensitive.append(f"Username in {key}: {u}")
        return list(dict.fromkeys(sensitive))
