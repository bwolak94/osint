"""Perspective Distorter Scanner — image analysis and perspective transform guidance for OSINT.

OPSEC intelligence value:
  - Correcting camera perspective reveals true building/sign dimensions for height estimation.
  - Detecting high-contrast rectangular regions (signs, licence plates, banners) in imagery
    enables targeted OCR or manual reading after transform.
  - Understanding image geometry (focal length, tilt) supports chronolocation by matching
    shadow angles to solar position calculators.
  - Base64 thumbnail allows analysts to preview content without leaving the platform.

Input entities:  URL (pointing to JPEG/PNG/TIFF/WebP)
Output entities:
  - image_metadata          — dimensions, format, aspect ratio
  - text_regions            — list of detected rectangular high-contrast regions
  - thumbnail_base64        — 200x200 preview (JPEG, base64)
  - perspective_instructions — manual OpenCV correction code snippet
  - educational_note        — OSINT image geometry analysis methodology
"""

from __future__ import annotations

import base64
import io
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_MAX_DOWNLOAD_BYTES = 15 * 1024 * 1024  # 15 MB
_HEADERS = {"User-Agent": "OSINT-Platform/1.0 contact@example.com"}

_EDUCATIONAL_NOTE = (
    "Perspective correction in OSINT image analysis: "
    "1) Keystone correction — correct trapezoidal distortion from off-axis camera angle. "
    "2) Four-point transform — select known rectangle corners (door frame, window, sign) to "
    "   unwarp to a standardised frontal view. OpenCV getPerspectiveTransform() achieves this. "
    "3) Homography — compute transformation matrix H from 4+ point correspondences between "
    "   distorted and reference views. Useful for plate/sign OCR after correction. "
    "4) Focal-length estimation — using known object sizes (standard car width = ~1.9 m) to "
    "   compute approximate distance to subject via similar-triangles geometry. "
    "5) Shadow analysis — after correcting image tilt, shadow direction in the corrected view "
    "   can be measured with a protractor for sun-angle/time estimation."
)

_OPENCV_INSTRUCTION_TEMPLATE = """# OpenCV perspective correction — manual 4-point transform
# Install: pip install opencv-python numpy

import cv2
import numpy as np

img = cv2.imread('downloaded_image.jpg')

# Select four corners of the target rectangle IN ORDER: top-left, top-right, bottom-right, bottom-left
# (Replace with actual pixel coordinates from your image inspection)
src_points = np.float32([
    [tl_x, tl_y],   # top-left corner of sign/door/window
    [tr_x, tr_y],   # top-right corner
    [br_x, br_y],   # bottom-right corner
    [bl_x, bl_y],   # bottom-left corner
])

# Desired output dimensions (adjust to match known aspect ratio of target object)
dst_w, dst_h = 800, 600
dst_points = np.float32([
    [0, 0],
    [dst_w, 0],
    [dst_w, dst_h],
    [0, dst_h],
])

# Compute and apply perspective transform
M = cv2.getPerspectiveTransform(src_points, dst_points)
warped = cv2.warpPerspective(img, M, (dst_w, dst_h))
cv2.imwrite('corrected.jpg', warped)
print('Saved corrected.jpg')
"""


class PerspectiveDistorterScanner(BaseOsintScanner):
    """Analyse image geometry and provide perspective correction instructions.

    Input:  ScanInputType.URL — must resolve to an image.
    Output: image_metadata, text_regions, thumbnail_base64, perspective_instructions.

    Optional Python dependencies:
      - Pillow >= 10.0 (pip install Pillow) — image processing
    """

    scanner_name = "perspective_distorter"
    supported_input_types = frozenset({ScanInputType.URL})
    cache_ttl = 3600

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        url = input_value
        content_type, raw_bytes = await self._fetch_content(url)
        if not raw_bytes:
            return {
                "url": url,
                "found": False,
                "error": "Failed to download image",
                "image_metadata": {},
                "text_regions": [],
                "thumbnail_base64": None,
                "perspective_instructions": _OPENCV_INSTRUCTION_TEMPLATE,
                "educational_note": _EDUCATIONAL_NOTE,
                "extracted_identifiers": [],
            }

        return self._analyse_image(url, raw_bytes, content_type)

    # ------------------------------------------------------------------
    # HTTP fetch
    # ------------------------------------------------------------------

    async def _fetch_content(self, url: str) -> tuple[str, bytes]:
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
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
            log.warning("Perspective fetch HTTP error", url=url, status=exc.response.status_code)
            return "", b""
        except Exception as exc:
            log.error("Perspective fetch failed", url=url, error=str(exc))
            return "", b""

    # ------------------------------------------------------------------
    # Image analysis
    # ------------------------------------------------------------------

    def _analyse_image(self, url: str, data: bytes, content_type: str) -> dict[str, Any]:
        try:
            from PIL import Image, ImageFilter
        except ImportError:
            return {
                "url": url,
                "found": False,
                "error": "Pillow not installed. Run: pip install Pillow",
                "image_metadata": {},
                "text_regions": [],
                "thumbnail_base64": None,
                "perspective_instructions": _OPENCV_INSTRUCTION_TEMPLATE,
                "educational_note": _EDUCATIONAL_NOTE,
                "extracted_identifiers": [],
            }

        try:
            img = Image.open(io.BytesIO(data))
        except Exception as exc:
            return {
                "url": url,
                "found": False,
                "error": f"Image open failed: {exc}",
                "image_metadata": {},
                "text_regions": [],
                "thumbnail_base64": None,
                "perspective_instructions": _OPENCV_INSTRUCTION_TEMPLATE,
                "educational_note": _EDUCATIONAL_NOTE,
                "extracted_identifiers": [],
            }

        width, height = img.size
        aspect_ratio = round(width / height, 4) if height else 0.0

        metadata: dict[str, Any] = {
            "format": img.format,
            "mode": img.mode,
            "width": width,
            "height": height,
            "aspect_ratio": aspect_ratio,
            "file_size_bytes": len(data),
            "content_type": content_type,
        }

        # Detect perspective distortion indicators from aspect ratio
        perspective_hints = self._classify_perspective(aspect_ratio, width, height)

        # Find high-contrast rectangular candidate regions (potential signs/plates/text)
        text_regions = self._detect_text_regions(img)

        # Build thumbnail
        thumbnail_b64 = self._make_thumbnail(img)

        # Estimate whether image has significant perspective distortion
        distortion_score = self._estimate_distortion_score(img)

        return {
            "url": url,
            "found": True,
            "image_metadata": metadata,
            "perspective_hints": perspective_hints,
            "distortion_score": distortion_score,
            "text_regions": text_regions,
            "thumbnail_base64": thumbnail_b64,
            "perspective_instructions": _OPENCV_INSTRUCTION_TEMPLATE,
            "educational_note": _EDUCATIONAL_NOTE,
            "extracted_identifiers": [],
        }

    # ------------------------------------------------------------------
    # Perspective classification
    # ------------------------------------------------------------------

    def _classify_perspective(self, aspect_ratio: float, width: int, height: int) -> list[str]:
        hints = []
        if aspect_ratio > 2.5:
            hints.append("Very wide panoramic — possible 360° or stitched composite image")
        elif aspect_ratio > 1.7:
            hints.append("Wide landscape — typical of building facade or street photography")
        elif 0.9 <= aspect_ratio <= 1.1:
            hints.append("Near-square — common in social media posts or drone nadir view")
        elif aspect_ratio < 0.6:
            hints.append("Tall portrait — likely mobile phone vertical capture; significant keystoning if building")

        if width >= 3000 or height >= 3000:
            hints.append("High resolution (≥3 MP) — sufficient for sub-region cropping and perspective correction")
        elif width <= 640 or height <= 640:
            hints.append("Low resolution — perspective correction will yield limited detail")

        return hints

    # ------------------------------------------------------------------
    # Text region detection (high-contrast rectangular blobs)
    # ------------------------------------------------------------------

    def _detect_text_regions(self, img: Any) -> list[dict[str, Any]]:
        """Scan for rectangular high-contrast regions likely containing text/plates."""
        try:
            from PIL import ImageFilter

            # Convert to greyscale and apply edge detection
            gray = img.convert("L")
            edges = gray.filter(ImageFilter.FIND_EDGES)
            w, h = edges.size

            # Sample grid of 8x8 blocks; flag blocks with high edge density
            block_w = max(w // 8, 1)
            block_h = max(h // 8, 1)
            regions: list[dict[str, Any]] = []

            for row in range(8):
                for col in range(8):
                    x0 = col * block_w
                    y0 = row * block_h
                    x1 = min(x0 + block_w, w)
                    y1 = min(y0 + block_h, h)
                    block = edges.crop((x0, y0, x1, y1))
                    pixels = list(block.getdata())
                    if not pixels:
                        continue
                    avg_edge = sum(pixels) / len(pixels)
                    # High average edge value in this block suggests text or fine structure
                    if avg_edge > 40:
                        regions.append({
                            "x": x0,
                            "y": y0,
                            "width": x1 - x0,
                            "height": y1 - y0,
                            "edge_density": round(avg_edge / 255.0, 4),
                            "confidence": "high" if avg_edge > 80 else "medium",
                        })

            # Limit to top-10 by edge density
            regions.sort(key=lambda r: r["edge_density"], reverse=True)
            return regions[:10]
        except Exception as exc:
            log.warning("Text region detection failed", error=str(exc))
            return []

    # ------------------------------------------------------------------
    # Distortion score
    # ------------------------------------------------------------------

    def _estimate_distortion_score(self, img: Any) -> float:
        """Heuristic: compare horizontal vs vertical gradient magnitudes.
        High imbalance suggests significant perspective tilt."""
        try:
            from PIL import ImageFilter

            gray = img.convert("L").resize((128, 128))
            h_edges = gray.filter(ImageFilter.Kernel(3, [-1, 0, 1, -2, 0, 2, -1, 0, 1], 1, 128))
            v_edges = gray.filter(ImageFilter.Kernel(3, [-1, -2, -1, 0, 0, 0, 1, 2, 1], 1, 128))
            h_vals = list(h_edges.getdata())
            v_vals = list(v_edges.getdata())
            if not h_vals or not v_vals:
                return 0.0
            avg_h = sum(h_vals) / len(h_vals)
            avg_v = sum(v_vals) / len(v_vals)
            total = avg_h + avg_v
            if total == 0:
                return 0.0
            imbalance = abs(avg_h - avg_v) / total
            return round(min(imbalance, 1.0), 4)
        except Exception:
            return 0.0

    # ------------------------------------------------------------------
    # Thumbnail
    # ------------------------------------------------------------------

    def _make_thumbnail(self, img: Any) -> str | None:
        try:
            thumb = img.copy().convert("RGB")
            thumb.thumbnail((200, 200))
            buf = io.BytesIO()
            thumb.save(buf, format="JPEG", quality=70)
            return base64.b64encode(buf.getvalue()).decode()
        except Exception:
            return None

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
