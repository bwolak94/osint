"""Forensic Image Auditor Scanner — Error Level Analysis (ELA) and metadata consistency checks.

OPSEC intelligence value:
  - ELA reveals image manipulation: re-saved or composited regions exhibit higher JPEG
    recompression error than the original background, exposing spliced elements.
  - Metadata inconsistency (creation date after modification date, mismatched software tags,
    thumbnail vs main image discrepancy) signals post-capture editing.
  - Software field in EXIF exposes editing tools: Photoshop, GIMP, Snapseed, Stable Diffusion
    — useful for attribution of manipulated imagery in disinformation investigations.
  - Thumbnail mismatch (embedded JPEG thumbnail differs from main image) is a classic forensic
    indicator of cropping or content replacement after original capture.

Input entities:  URL (pointing to JPEG/PNG/TIFF/WebP)
Output entities:
  - ela_result              — mean_error, max_error, std_dev, high_error_ratio, is_suspicious
  - original_exif_software  — software tag from EXIF
  - manipulation_indicators — list of detected manipulation signals
  - confidence_score        — float 0-1 (likelihood of manipulation)
  - educational_note        — ELA methodology explanation
"""

from __future__ import annotations

import io
import math
import struct
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024  # 20 MB
_ELA_QUALITY = 95  # Re-save quality for ELA
_ELA_HIGH_ERROR_THRESHOLD = 40  # Pixel error magnitude threshold for "high error"
_ELA_SUSPICIOUS_RATIO = 0.15  # If >15% pixels exceed threshold → suspicious
_HEADERS = {"User-Agent": "OSINT-Platform/1.0 (Forensic OSINT) contact@example.com"}

_EDUCATIONAL_NOTE = (
    "Error Level Analysis (ELA) methodology: "
    "JPEG compression is lossy — each successive save at a given quality level introduces a "
    "predictable, decreasing residual error. When an image is manipulated and re-saved, the "
    "spliced region has undergone fewer compression cycles than the background, so it shows a "
    "higher ELA error (brighter in ELA visualisation). "
    "Steps: 1) Re-save original as JPEG at quality=95. "
    "2) Compute per-pixel absolute difference between original and re-saved version. "
    "3) Normalise differences to 0-255. "
    "4) High-error regions (>threshold) clustered away from edges suggest manipulation. "
    "Limitations: ELA is a heuristic — false positives occur with high-quality originals, "
    "and images that have already been heavily compressed (social media) may show uniform "
    "high error across the entire frame. Always corroborate with metadata analysis. "
    "Tools: FotoForensics.com provides online ELA; Ghiro is an open-source forensics platform."
)

_KNOWN_EDITING_SOFTWARE = {
    "adobe photoshop", "gimp", "adobe lightroom", "snapseed", "facetune",
    "meitu", "pixlr", "canva", "affinity photo", "capture one",
    "stable diffusion", "dall-e", "midjourney", "adobe firefly",
    "comfyui", "automatic1111",
}


class ForensicImageAuditorScanner(BaseOsintScanner):
    """Perform ELA and metadata forensics on an image URL.

    Input:  ScanInputType.URL — must resolve to a JPEG, PNG, TIFF, or WebP image.
    Output: ela_result dict, original_exif_software, manipulation_indicators, confidence_score.

    Optional Python dependencies:
      - Pillow >= 10.0 (pip install Pillow) — image processing and ELA
    """

    scanner_name = "forensic_image_auditor"
    supported_input_types = frozenset({ScanInputType.URL})
    cache_ttl = 86400

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        url = input_value
        content_type, raw_bytes = await self._fetch_content(url)

        if not raw_bytes:
            return {
                "url": url,
                "found": False,
                "error": "Failed to download image",
                "ela_result": {},
                "original_exif_software": "",
                "manipulation_indicators": [],
                "confidence_score": 0.0,
                "educational_note": _EDUCATIONAL_NOTE,
                "extracted_identifiers": [],
            }

        return self._audit_image(url, raw_bytes, content_type)

    # ------------------------------------------------------------------
    # HTTP fetch
    # ------------------------------------------------------------------

    async def _fetch_content(self, url: str) -> tuple[str, bytes]:
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(45.0),
                follow_redirects=True,
                headers=_HEADERS,
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
            log.warning("Forensic fetch HTTP error", url=url, status=exc.response.status_code)
            return "", b""
        except Exception as exc:
            log.error("Forensic fetch failed", url=url, error=str(exc))
            return "", b""

    # ------------------------------------------------------------------
    # Main audit
    # ------------------------------------------------------------------

    def _audit_image(self, url: str, data: bytes, content_type: str) -> dict[str, Any]:
        try:
            from PIL import Image, ImageChops
        except ImportError:
            return {
                "url": url,
                "found": False,
                "error": "Pillow not installed. Run: pip install Pillow",
                "ela_result": {},
                "original_exif_software": "",
                "manipulation_indicators": [],
                "confidence_score": 0.0,
                "educational_note": _EDUCATIONAL_NOTE,
                "extracted_identifiers": [],
            }

        try:
            original_img = Image.open(io.BytesIO(data))
        except Exception as exc:
            return {
                "url": url,
                "found": False,
                "error": f"Image open failed: {exc}",
                "ela_result": {},
                "original_exif_software": "",
                "manipulation_indicators": [],
                "confidence_score": 0.0,
                "educational_note": _EDUCATIONAL_NOTE,
                "extracted_identifiers": [],
            }

        manipulation_indicators: list[str] = []

        # Extract EXIF metadata
        exif_data = self._extract_exif(original_img)
        exif_software = exif_data.get("Software", "")
        exif_make = exif_data.get("Make", "")
        exif_model = exif_data.get("Model", "")
        creation_dt = exif_data.get("DateTimeOriginal", exif_data.get("DateTime", ""))
        modification_dt = exif_data.get("DateTimeDigitized", "")

        # Check for known editing software signatures
        if exif_software and any(sw in exif_software.lower() for sw in _KNOWN_EDITING_SOFTWARE):
            manipulation_indicators.append(
                f"editing_software_detected: {exif_software!r} is a known image editing tool"
            )

        # Check date consistency
        if creation_dt and modification_dt and creation_dt > modification_dt:
            manipulation_indicators.append(
                "timestamp_anomaly: creation date appears after modification date"
            )

        # Check thumbnail vs main image mismatch
        thumbnail_mismatch = self._check_thumbnail_mismatch(original_img, data)
        if thumbnail_mismatch:
            manipulation_indicators.append(
                "thumbnail_mismatch: embedded JPEG thumbnail dimensions differ from main image"
            )

        # Perform ELA
        ela_result = self._perform_ela(original_img, ImageChops)
        if ela_result.get("is_suspicious"):
            manipulation_indicators.append(
                f"ela_suspicious: high-error pixel ratio {ela_result.get('high_error_ratio', 0):.3f} "
                f"exceeds threshold {_ELA_SUSPICIOUS_RATIO}"
            )

        # No camera make/model = possibly software-generated or stripped metadata
        if not exif_make and not exif_model:
            if original_img.format in ("JPEG", "JPG"):
                manipulation_indicators.append(
                    "missing_camera_metadata: no Make/Model EXIF tags in a JPEG file "
                    "(common in AI-generated or heavily edited images)"
                )

        # Confidence score: weighted combination of signals
        score = self._compute_confidence(ela_result, manipulation_indicators)

        return {
            "url": url,
            "found": True,
            "image_format": original_img.format,
            "image_size": list(original_img.size),
            "ela_result": ela_result,
            "original_exif_software": exif_software,
            "exif_make": exif_make,
            "exif_model": exif_model,
            "exif_creation_date": creation_dt,
            "exif_modification_date": modification_dt,
            "manipulation_indicators": manipulation_indicators,
            "confidence_score": score,
            "is_likely_manipulated": score > 0.5 or len(manipulation_indicators) >= 2,
            "educational_note": _EDUCATIONAL_NOTE,
            "extracted_identifiers": [f"software:{exif_software}"] if exif_software else [],
        }

    # ------------------------------------------------------------------
    # ELA implementation
    # ------------------------------------------------------------------

    def _perform_ela(self, original_img: Any, ImageChops: Any) -> dict[str, Any]:
        """Run Error Level Analysis by re-saving at quality=95 and diffing."""
        try:
            # Convert to RGB for consistent JPEG round-trip
            img_rgb = original_img.convert("RGB")
            buf = io.BytesIO()
            img_rgb.save(buf, format="JPEG", quality=_ELA_QUALITY)
            buf.seek(0)
            resaved = __import__("PIL").Image.open(buf).convert("RGB")

            # Compute absolute pixel difference
            diff = ImageChops.difference(img_rgb, resaved)
            diff_pixels = list(diff.getdata())

            if not diff_pixels:
                return {
                    "is_suspicious": False,
                    "mean_error": 0.0,
                    "max_error": 0,
                    "std_dev": 0.0,
                    "high_error_ratio": 0.0,
                }

            # Per-pixel magnitude = average of R, G, B channel errors
            magnitudes = [
                (p[0] + p[1] + p[2]) / 3.0
                for p in diff_pixels
            ]
            total = len(magnitudes)
            mean_error = sum(magnitudes) / total
            max_error = max(magnitudes)
            variance = sum((m - mean_error) ** 2 for m in magnitudes) / total
            std_dev = math.sqrt(variance)
            high_error_count = sum(1 for m in magnitudes if m > _ELA_HIGH_ERROR_THRESHOLD)
            high_error_ratio = high_error_count / total

            return {
                "is_suspicious": high_error_ratio > _ELA_SUSPICIOUS_RATIO,
                "mean_error": round(mean_error, 4),
                "max_error": round(max_error, 2),
                "std_dev": round(std_dev, 4),
                "high_error_ratio": round(high_error_ratio, 6),
                "high_error_threshold": _ELA_HIGH_ERROR_THRESHOLD,
                "suspicious_threshold": _ELA_SUSPICIOUS_RATIO,
            }
        except Exception as exc:
            log.warning("ELA computation failed", error=str(exc))
            return {
                "is_suspicious": False,
                "error": str(exc),
                "mean_error": 0.0,
                "max_error": 0,
                "std_dev": 0.0,
                "high_error_ratio": 0.0,
            }

    # ------------------------------------------------------------------
    # EXIF extraction
    # ------------------------------------------------------------------

    def _extract_exif(self, img: Any) -> dict[str, str]:
        """Extract human-readable EXIF tags."""
        try:
            from PIL.ExifTags import TAGS
            raw_exif = img._getexif()  # type: ignore[attr-defined]
            if not raw_exif:
                return {}
            return {
                TAGS.get(tag_id, str(tag_id)): (
                    str(value)[:200] if not isinstance(value, (bytes, bytearray)) else value.hex()[:200]
                )
                for tag_id, value in raw_exif.items()
                if not isinstance(value, dict)  # Skip nested IFDs
            }
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Thumbnail mismatch check
    # ------------------------------------------------------------------

    def _check_thumbnail_mismatch(self, img: Any, raw_data: bytes) -> bool:
        """Check whether embedded thumbnail dimensions differ from main image."""
        try:
            from PIL import Image, ImageFile
            ImageFile.LOAD_TRUNCATED_IMAGES = True

            # Extract thumbnail from EXIF
            exif_raw = img._getexif()  # type: ignore[attr-defined]
            if not exif_raw:
                return False

            # EXIF thumbnail tag IDs: 513 (JPEGInterchangeFormat start), 514 (length)
            thumb_offset = exif_raw.get(513)
            thumb_length = exif_raw.get(514)
            if not thumb_offset or not thumb_length:
                return False

            # Extract thumbnail bytes from raw data (after EXIF header offset)
            # This is a best-effort check; exact byte offset varies
            try:
                thumb_data = raw_data[thumb_offset: thumb_offset + thumb_length]
                if len(thumb_data) < 100:
                    return False
                thumb_img = Image.open(io.BytesIO(thumb_data))
                main_w, main_h = img.size
                thumb_w, thumb_h = thumb_img.size
                # Flag if thumbnail aspect ratio differs significantly from main
                main_ratio = main_w / max(main_h, 1)
                thumb_ratio = thumb_w / max(thumb_h, 1)
                return abs(main_ratio - thumb_ratio) > 0.2
            except Exception:
                return False
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Confidence scoring
    # ------------------------------------------------------------------

    def _compute_confidence(self, ela_result: dict[str, Any], indicators: list[str]) -> float:
        """Compute weighted confidence score (0-1) that image is manipulated."""
        score = 0.0

        # ELA contribution
        high_error_ratio = ela_result.get("high_error_ratio", 0.0)
        score += min(high_error_ratio * 2, 0.5)  # max 0.5 from ELA

        # Each indicator adds weight
        indicator_weights = {
            "editing_software_detected": 0.3,
            "thumbnail_mismatch": 0.25,
            "timestamp_anomaly": 0.15,
            "ela_suspicious": 0.2,
            "missing_camera_metadata": 0.1,
        }
        for indicator in indicators:
            for key, weight in indicator_weights.items():
                if indicator.startswith(key):
                    score += weight
                    break

        return round(min(score, 1.0), 4)

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
