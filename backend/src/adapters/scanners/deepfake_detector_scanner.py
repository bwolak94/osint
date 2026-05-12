"""Deepfake Detector Scanner — AI-generation artifact analysis for images and videos.

OPSEC intelligence value:
  - Identifies potentially AI-generated or manipulated imagery used in disinformation campaigns.
  - GAN fingerprints (spectral artifacts, symmetry anomalies) can reveal synthetic media.
  - Heuristic checks expose unusual pixel-value distributions and skin-tone uniformity
    characteristic of many text-to-image and face-swap models.

Input entities:  URL (pointing to JPEG/PNG/TIFF/WebP or video file)
Output entities:
  - is_suspicious        — boolean flag
  - confidence_score     — float 0-1 (higher = more likely AI-generated)
  - detected_artifacts   — list of named artifact types found
  - metadata             — image dimensions, format, file size
  - educational_note     — explanation of GAN fingerprinting methodology
"""

from __future__ import annotations

import base64
import io
import os
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024  # 20 MB
_INVID_ENDPOINT = "https://api.weverify.eu/submit/"
_HEADERS = {"User-Agent": "OSINT-Platform/1.0 contact@example.com"}

_EDUCATIONAL_NOTE = (
    "GAN (Generative Adversarial Network) models leave characteristic fingerprints: "
    "checkerboard artifacts in frequency domain (from transposed convolutions), "
    "unnatural symmetry in facial features, blurring at hair/background boundaries, "
    "and unusually uniform skin-tone pixel distributions. Error Level Analysis (ELA) "
    "can reveal double-compression artifacts typical of re-saved synthetic images. "
    "Tools like InVID/WeVerify aggregate multiple signals into a confidence score."
)


class DeepfakeDetectorScanner(BaseOsintScanner):
    """Analyse a media URL for signs of AI generation or manipulation.

    Input:  ScanInputType.URL — must resolve to an image or video.
    Output: is_suspicious, confidence_score, detected_artifacts, metadata.

    Optional Python dependencies (graceful fallback if missing):
      - Pillow >= 10.0 (pip install Pillow) — heuristic pixel analysis
    Optional environment variables:
      - INVID_API_KEY — WeVerify/InVID API key for authoritative analysis
    """

    scanner_name = "deepfake_detector"
    supported_input_types = frozenset({ScanInputType.URL})
    cache_ttl = 3600

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        url = input_value
        invid_api_key = os.getenv("INVID_API_KEY")

        content_type, raw_bytes = await self._fetch_content(url)
        if not raw_bytes:
            return {
                "url": url,
                "found": False,
                "error": "Failed to download content",
                "is_suspicious": False,
                "confidence_score": 0.0,
                "detected_artifacts": [],
                "metadata": {},
                "educational_note": _EDUCATIONAL_NOTE,
                "extracted_identifiers": [],
            }

        metadata = {
            "content_type": content_type,
            "file_size_bytes": len(raw_bytes),
            "url": url,
        }

        # Priority: InVID/WeVerify API if key is available
        if invid_api_key:
            invid_result = await self._query_invid(url, invid_api_key)
            if invid_result.get("success"):
                return {
                    "url": url,
                    "found": True,
                    "source": "invid_weverify",
                    "is_suspicious": invid_result.get("is_suspicious", False),
                    "confidence_score": invid_result.get("confidence_score", 0.0),
                    "detected_artifacts": invid_result.get("detected_artifacts", []),
                    "metadata": {**metadata, **invid_result.get("metadata", {})},
                    "educational_note": _EDUCATIONAL_NOTE,
                    "extracted_identifiers": [],
                }

        # Fallback: heuristic Pillow-based analysis
        return self._heuristic_analysis(url, raw_bytes, metadata)

    # ------------------------------------------------------------------
    # HTTP fetch
    # ------------------------------------------------------------------

    async def _fetch_content(self, url: str) -> tuple[str, bytes]:
        """Stream-download up to _MAX_DOWNLOAD_BYTES."""
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
            log.warning("Deepfake fetch HTTP error", url=url, status=exc.response.status_code)
            return "", b""
        except Exception as exc:
            log.error("Deepfake fetch failed", url=url, error=str(exc))
            return "", b""

    # ------------------------------------------------------------------
    # InVID / WeVerify API
    # ------------------------------------------------------------------

    async def _query_invid(self, url: str, api_key: str) -> dict[str, Any]:
        """Submit media URL to InVID/WeVerify for analysis."""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    _INVID_ENDPOINT,
                    json={"url": url},
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "User-Agent": "OSINT-Platform/1.0",
                    },
                )
                if resp.status_code != 200:
                    log.warning("InVID API error", status=resp.status_code)
                    return {"success": False}

                data = resp.json()
                # Normalise InVID response shape
                score = float(data.get("manipulationScore") or data.get("score") or 0.0)
                artifacts = data.get("detectedArtifacts") or data.get("artifacts") or []
                return {
                    "success": True,
                    "is_suspicious": score > 0.5,
                    "confidence_score": round(min(score, 1.0), 4),
                    "detected_artifacts": artifacts,
                    "metadata": {
                        "invid_verdict": data.get("verdict", ""),
                        "invid_model": data.get("model", ""),
                    },
                }
        except Exception as exc:
            log.warning("InVID API call failed", url=url, error=str(exc))
            return {"success": False}

    # ------------------------------------------------------------------
    # Heuristic Pillow analysis
    # ------------------------------------------------------------------

    def _heuristic_analysis(self, url: str, data: bytes, metadata: dict[str, Any]) -> dict[str, Any]:
        try:
            from PIL import Image, ImageStat
        except ImportError:
            return {
                "url": url,
                "found": False,
                "error": "Pillow not installed. Run: pip install Pillow",
                "is_suspicious": False,
                "confidence_score": 0.0,
                "detected_artifacts": [],
                "metadata": metadata,
                "educational_note": _EDUCATIONAL_NOTE,
                "extracted_identifiers": [],
            }

        try:
            img = Image.open(io.BytesIO(data))
            img_rgb = img.convert("RGB")
        except Exception as exc:
            return {
                "url": url,
                "found": False,
                "error": f"Image parse error: {exc}",
                "is_suspicious": False,
                "confidence_score": 0.0,
                "detected_artifacts": [],
                "metadata": metadata,
                "educational_note": _EDUCATIONAL_NOTE,
                "extracted_identifiers": [],
            }

        width, height = img_rgb.size
        metadata.update({"width": width, "height": height, "format": img.format, "mode": img.mode})

        artifacts: list[str] = []
        scores: list[float] = []

        # 1. Skin-tone uniformity check (blobs of very similar hue → GAN face generation)
        skin_uniformity_score = self._check_skin_tone_uniformity(img_rgb)
        scores.append(skin_uniformity_score)
        if skin_uniformity_score > 0.6:
            artifacts.append("unusual_skin_tone_uniformity")

        # 2. Symmetric noise pattern check (horizontal pixel variance symmetry)
        symmetry_score = self._check_horizontal_symmetry(img_rgb)
        scores.append(symmetry_score)
        if symmetry_score > 0.7:
            artifacts.append("symmetric_noise_pattern")

        # 3. Frequency domain uniformity (GAN checkerboard artifacts)
        freq_score = self._check_frequency_artifacts(img_rgb)
        scores.append(freq_score)
        if freq_score > 0.5:
            artifacts.append("frequency_domain_artifacts")

        # 4. Statistical channel analysis
        stat = ImageStat.Stat(img_rgb)
        r_std, g_std, b_std = stat.stddev
        channel_balance_score = 1.0 - (abs(r_std - g_std) + abs(g_std - b_std)) / (max(r_std, g_std, b_std, 1) * 2)
        scores.append(channel_balance_score * 0.3)  # weaker signal
        if channel_balance_score > 0.92:
            artifacts.append("unnatural_channel_balance")

        # 5. Aspect ratio check — many GAN models produce specific square ratios
        ratio = width / height if height else 1.0
        if abs(ratio - 1.0) < 0.01 and width in (256, 512, 1024):
            artifacts.append("gan_canonical_resolution")
            scores.append(0.4)

        confidence = round(min(sum(scores) / max(len(scores), 1), 1.0), 4)
        is_suspicious = confidence > 0.45 or len(artifacts) >= 2

        # Build small base64 thumbnail for frontend preview
        thumb = img_rgb.copy()
        thumb.thumbnail((200, 200))
        buf = io.BytesIO()
        thumb.save(buf, format="JPEG", quality=70)
        thumbnail_b64 = base64.b64encode(buf.getvalue()).decode()

        return {
            "url": url,
            "found": True,
            "source": "heuristic_pillow",
            "is_suspicious": is_suspicious,
            "confidence_score": confidence,
            "detected_artifacts": artifacts,
            "metadata": metadata,
            "thumbnail_base64": thumbnail_b64,
            "educational_note": _EDUCATIONAL_NOTE,
            "extracted_identifiers": [],
        }

    # ------------------------------------------------------------------
    # Heuristic helpers
    # ------------------------------------------------------------------

    def _check_skin_tone_uniformity(self, img_rgb: Any) -> float:
        """Score how uniform the skin-coloured pixel distribution is (0-1)."""
        try:
            pixels = list(img_rgb.getdata())
            skin_pixels = [
                p for p in pixels
                if 60 <= p[0] <= 255 and 40 <= p[1] <= 200 and 20 <= p[2] <= 160
                and p[0] > p[2]  # red channel dominates
            ]
            if not skin_pixels:
                return 0.0
            skin_ratio = len(skin_pixels) / max(len(pixels), 1)
            if skin_ratio < 0.05:
                return 0.0
            # Compute variance of skin pixel values
            avg_r = sum(p[0] for p in skin_pixels) / len(skin_pixels)
            variance = sum((p[0] - avg_r) ** 2 for p in skin_pixels) / len(skin_pixels)
            # Low variance in large skin blobs is suspicious
            normalised_variance = min(variance / 1000.0, 1.0)
            return round(max(0.0, skin_ratio * (1.0 - normalised_variance)), 4)
        except Exception:
            return 0.0

    def _check_horizontal_symmetry(self, img_rgb: Any) -> float:
        """Detect unnatural left-right pixel value symmetry (GAN face artefact)."""
        try:
            width, height = img_rgb.size
            if width < 64 or height < 64:
                return 0.0
            # Sample central horizontal strip
            strip_y = height // 2
            left_pixels = [img_rgb.getpixel((x, strip_y)) for x in range(width // 4, width // 2)]
            right_pixels = [
                img_rgb.getpixel((width - 1 - x, strip_y))
                for x in range(width // 4, width // 2)
            ]
            if not left_pixels:
                return 0.0
            diffs = [abs(l[0] - r[0]) + abs(l[1] - r[1]) + abs(l[2] - r[2]) for l, r in zip(left_pixels, right_pixels)]
            mean_diff = sum(diffs) / (len(diffs) * 765.0)  # 765 = 255*3 max
            # Lower mean_diff → higher symmetry → higher suspicion score
            return round(max(0.0, 1.0 - mean_diff * 8), 4)
        except Exception:
            return 0.0

    def _check_frequency_artifacts(self, img_rgb: Any) -> float:
        """Detect GAN checkerboard artifacts via pixel-stride variance analysis."""
        try:
            gray = img_rgb.convert("L")
            width, height = gray.size
            if width < 32 or height < 32:
                return 0.0
            # Sample pixels at even/odd stride positions
            even_vals = []
            odd_vals = []
            for y in range(0, min(height, 256), 2):
                for x in range(0, min(width, 256), 2):
                    even_vals.append(gray.getpixel((x, y)))
                    if x + 1 < width:
                        odd_vals.append(gray.getpixel((x + 1, y)))

            if not even_vals or not odd_vals:
                return 0.0

            avg_even = sum(even_vals) / len(even_vals)
            avg_odd = sum(odd_vals) / len(odd_vals)
            # Significant systematic difference between even/odd columns → checkerboard
            stride_diff = abs(avg_even - avg_odd) / 255.0
            return round(min(stride_diff * 10, 1.0), 4)
        except Exception:
            return 0.0

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
