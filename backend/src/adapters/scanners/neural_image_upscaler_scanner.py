"""Neural Image Upscaler — analyses image quality and provides AI upscaling recommendations for OSINT enhancement."""
import io
import math
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_UPSCALING_SERVICES: list[dict[str, str]] = [
    {
        "name": "Upscayl (Desktop App)",
        "url": "https://upscayl.org",
        "description": "Free, open-source, runs locally — best for sensitive images (no upload required)",
        "model": "Real-ESRGAN, BSRGAN, SwinIR",
        "max_scale": "4x",
    },
    {
        "name": "Real-ESRGAN Online",
        "url": "https://huggingface.co/spaces/akhaliq/Real-ESRGAN",
        "description": "Free HuggingFace Space — Real-ESRGAN model, up to 4x upscaling",
        "model": "Real-ESRGAN",
        "max_scale": "4x",
    },
    {
        "name": "Waifu2x",
        "url": "https://waifu2x.udp.jp",
        "description": "Free, specialised for anime/illustration but also handles photos",
        "model": "Waifu2x CNN",
        "max_scale": "2x",
    },
    {
        "name": "Bigjpg",
        "url": "https://bigjpg.com",
        "description": "AI upscaling for photos and illustrations, free tier available",
        "model": "Bigjpg CNN",
        "max_scale": "16x",
    },
    {
        "name": "ImgUpscaler",
        "url": "https://imgupscaler.com",
        "description": "Free AI upscaler with noise reduction",
        "model": "Real-ESRGAN variant",
        "max_scale": "4x",
    },
    {
        "name": "Let's Enhance",
        "url": "https://letsenhance.io",
        "description": "Commercial upscaler with free trial, high quality output",
        "model": "Proprietary",
        "max_scale": "16x",
    },
]


def _estimate_sharpness(img: Any) -> float:
    """Estimate image sharpness using Laplacian variance approximation via Pillow."""
    try:
        from PIL import ImageFilter

        gray = img.convert("L")
        # Apply Laplacian filter to detect edges
        laplacian = gray.filter(ImageFilter.Kernel(
            size=3,
            kernel=[-1, -1, -1, -1, 8, -1, -1, -1, -1],
            scale=1,
            offset=0,
        ))
        pixels = list(laplacian.getdata())
        if not pixels:
            return 0.0
        mean = sum(pixels) / len(pixels)
        variance = sum((p - mean) ** 2 for p in pixels) / len(pixels)
        return round(math.sqrt(variance), 2)
    except Exception:
        return -1.0


def _estimate_noise_level(img: Any) -> float:
    """Estimate noise level by comparing original to blurred version using Pillow."""
    try:
        from PIL import ImageFilter

        gray = img.convert("L")
        blurred = gray.filter(ImageFilter.GaussianBlur(radius=2))

        orig_pixels = list(gray.getdata())
        blur_pixels = list(blurred.getdata())

        if not orig_pixels or len(orig_pixels) != len(blur_pixels):
            return -1.0

        diff_sq = sum((a - b) ** 2 for a, b in zip(orig_pixels, blur_pixels))
        mse = diff_sq / len(orig_pixels)
        return round(math.sqrt(mse), 2)
    except Exception:
        return -1.0


def _quality_label(sharpness: float, noise: float, width: int, height: int) -> str:
    """Simple heuristic quality classification."""
    if width < 200 or height < 200:
        return "Very Low — too small for reliable analysis"
    if sharpness < 5.0:
        return "Blurry — significant motion blur or out-of-focus"
    if noise > 20.0:
        return "Noisy — high sensor noise or heavy compression artefacts"
    if sharpness > 30.0 and noise < 10.0 and width >= 1000:
        return "High — suitable for direct analysis"
    return "Medium — upscaling may reveal additional detail"


class NeuralImageUpscalerScanner(BaseOsintScanner):
    """Downloads an image, analyses its quality, and recommends AI upscaling services for OSINT enhancement."""

    scanner_name = "neural_image_upscaler"
    supported_input_types = frozenset({ScanInputType.URL})
    cache_ttl = 3600

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        try:
            from PIL import Image
        except ImportError:
            return {"found": False, "error": "Pillow not installed — cannot analyse image"}

        # Fetch image
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(input_value, headers={"User-Agent": "Mozilla/5.0"})
                resp.raise_for_status()
                content_type = resp.headers.get("content-type", "")
                if "image" not in content_type:
                    return {
                        "found": False,
                        "error": f"URL does not point to an image (content-type: {content_type})",
                    }
                image_bytes = resp.content
                file_size_bytes = len(image_bytes)
        except Exception as exc:
            return {"found": False, "image_url": input_value, "error": f"Failed to fetch image: {exc}"}

        # Open and analyse image
        try:
            img = Image.open(io.BytesIO(image_bytes))
            width, height = img.size
            img_format = img.format or "Unknown"
            img_mode = img.mode
        except Exception as exc:
            return {"found": False, "image_url": input_value, "error": f"Failed to open image: {exc}"}

        # Quality metrics
        sharpness = _estimate_sharpness(img)
        noise_level = _estimate_noise_level(img)
        pixel_count = width * height
        megapixels = round(pixel_count / 1_000_000, 2)

        # Determine if upscaling is recommended
        needs_upscaling = width < 1000 or height < 1000
        upscale_factor_needed: int | None = None
        if needs_upscaling:
            target = 1000
            factor = math.ceil(max(target / width, target / height))
            upscale_factor_needed = min(factor, 4)  # Cap at 4x

        quality_label = _quality_label(sharpness, noise_level, width, height)

        # EXIF check for camera info
        camera_info: dict[str, str] = {}
        try:
            from PIL.ExifTags import TAGS
            raw_exif = img._getexif() or {}  # type: ignore[attr-defined]
            for tag_id, value in raw_exif.items():
                tag = TAGS.get(tag_id, str(tag_id))
                if tag in ("Make", "Model", "Software", "LensModel"):
                    camera_info[tag] = str(value)[:100]
        except Exception:
            pass

        # Suggest best service based on image type
        is_illustration = img_mode in ("P", "1") or (img_format in ("PNG", "GIF") and megapixels < 0.5)
        recommended_service = _UPSCALING_SERVICES[2]["name"] if is_illustration else _UPSCALING_SERVICES[0]["name"]

        return {
            "found": True,
            "image_url": input_value,
            "image_metadata": {
                "format": img_format,
                "mode": img_mode,
                "width_px": width,
                "height_px": height,
                "megapixels": megapixels,
                "file_size_bytes": file_size_bytes,
                "file_size_kb": round(file_size_bytes / 1024, 1),
            },
            "camera_info": camera_info,
            "quality_analysis": {
                "sharpness_score": sharpness,
                "noise_level": noise_level,
                "quality_label": quality_label,
                "needs_upscaling": needs_upscaling,
                "recommended_upscale_factor": upscale_factor_needed,
            },
            "upscaling_recommendation": (
                f"Upscale {upscale_factor_needed}x to reach minimum 1000px dimension"
                if needs_upscaling
                else "Image resolution is sufficient — upscaling optional for detail enhancement"
            ),
            "recommended_service": recommended_service,
            "upscaling_services": _UPSCALING_SERVICES,
            "educational_note": (
                "AI upscaling (Real-ESRGAN, SwinIR) uses deep learning to reconstruct high-frequency details "
                "lost during compression or downscaling. In OSINT, this can reveal license plates, faces, "
                "text, and background details invisible in low-resolution images. "
                "For sensitive investigations, use Upscayl locally to avoid uploading evidence to third-party servers."
            ),
        }
