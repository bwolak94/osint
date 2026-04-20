"""License Plate Decoder — detects and decodes license plates from image URLs using regex heuristics and optional API."""
import io
import os
import re
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Regex patterns keyed by country/region with format description
_PLATE_PATTERNS: list[dict[str, Any]] = [
    {
        "country": "Poland",
        "code": "PL",
        "pattern": re.compile(r"\b([A-Z]{2,3}\s?[A-Z0-9]{4,5})\b"),
        "description": "2-3 letter district code + 4-5 alphanumeric",
    },
    {
        "country": "Germany",
        "code": "DE",
        "pattern": re.compile(r"\b([A-Z]{1,3}[\s\-][A-Z]{1,2}\s?\d{1,4}[EH]?)\b"),
        "description": "1-3 letter city + 1-2 letter + 1-4 digits",
    },
    {
        "country": "United Kingdom",
        "code": "GB",
        "pattern": re.compile(r"\b([A-Z]{2}\d{2}\s?[A-Z]{3})\b"),
        "description": "2 letters + 2 digits + 3 letters (post-2001)",
    },
    {
        "country": "United States (generic)",
        "code": "US",
        "pattern": re.compile(r"\b([A-Z0-9]{2,3}[\s\-][A-Z0-9]{3,4})\b"),
        "description": "State-specific, generally 5-7 alphanumeric with separator",
    },
    {
        "country": "France",
        "code": "FR",
        "pattern": re.compile(r"\b([A-Z]{2}[\s\-]\d{3}[\s\-][A-Z]{2})\b"),
        "description": "2 letters - 3 digits - 2 letters (post-2009)",
    },
    {
        "country": "Spain",
        "code": "ES",
        "pattern": re.compile(r"\b(\d{4}\s?[BCDFGHJKLMNPRSTUVWXYZ]{3})\b"),
        "description": "4 digits + 3 consonants",
    },
    {
        "country": "Italy",
        "code": "IT",
        "pattern": re.compile(r"\b([A-Z]{2}\s?\d{3}\s?[A-Z]{2})\b"),
        "description": "2 letters + 3 digits + 2 letters",
    },
    {
        "country": "Netherlands",
        "code": "NL",
        "pattern": re.compile(r"\b([A-Z0-9]{2}[\s\-][A-Z0-9]{2}[\s\-][A-Z0-9]{2})\b"),
        "description": "3 groups of 2 alphanumeric characters",
    },
]

_PLATERECOGNIZER_ENDPOINT = "https://api.platerecognizer.com/v1/plate-reader/"


def _guess_country_from_text(text: str) -> list[dict[str, Any]]:
    """Run all regex patterns against OCR'd or provided text."""
    matches: list[dict[str, Any]] = []
    upper_text = text.upper()
    for entry in _PLATE_PATTERNS:
        found = entry["pattern"].findall(upper_text)
        for plate in found:
            matches.append({
                "plate_text": plate.strip(),
                "likely_country": entry["country"],
                "country_code": entry["code"],
                "format_description": entry["description"],
                "confidence": "heuristic",
            })
    return matches


class LicensePlateDecoderScanner(BaseOsintScanner):
    """Downloads an image and decodes license plates using PlateRecognizer API or heuristic regex patterns."""

    scanner_name = "license_plate_decoder"
    supported_input_types = frozenset({ScanInputType.URL})
    cache_ttl = 86400

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        api_key = os.getenv("PLATE_RECOGNIZER_API_KEY")

        # Fetch image bytes regardless — used for API and for basic image info
        image_bytes: bytes | None = None
        image_content_type = ""
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(input_value, headers={"User-Agent": "Mozilla/5.0"})
                resp.raise_for_status()
                image_content_type = resp.headers.get("content-type", "")
                if "image" not in image_content_type:
                    return {
                        "found": False,
                        "error": f"URL is not an image (content-type: {image_content_type})",
                    }
                image_bytes = resp.content
        except Exception as exc:
            return {"found": False, "image_url": input_value, "error": f"Failed to fetch image: {exc}"}

        plates: list[dict[str, Any]] = []

        # Path 1: PlateRecognizer API (high accuracy, requires key)
        if api_key and image_bytes:
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    pr_resp = await client.post(
                        _PLATERECOGNIZER_ENDPOINT,
                        headers={"Authorization": f"Token {api_key}"},
                        files={"upload": ("plate.jpg", image_bytes, image_content_type)},
                    )
                    pr_resp.raise_for_status()
                    pr_data = pr_resp.json()

                for result in pr_data.get("results", []):
                    candidates = result.get("candidates", [])
                    best = candidates[0] if candidates else {}
                    region = result.get("region", {})
                    vehicle = result.get("vehicle", {})
                    plates.append({
                        "plate_text": result.get("plate", "").upper(),
                        "confidence": round(result.get("score", 0.0), 4),
                        "likely_country": region.get("code", "unknown").upper(),
                        "region_score": round(region.get("score", 0.0), 4),
                        "vehicle_type": vehicle.get("type"),
                        "vehicle_score": round(vehicle.get("score", 0.0), 4),
                        "alternative_readings": [c.get("plate", "").upper() for c in candidates[1:3]],
                        "source": "platerecognizer_api",
                        "box": result.get("box"),
                    })
                log.info("license_plate_decoder: PlateRecognizer returned results", count=len(plates))
            except Exception as exc:
                log.warning("license_plate_decoder: PlateRecognizer API failed", error=str(exc))
                # Fall through to heuristic approach

        # Path 2: Attempt basic OCR via Pillow if no API results yet
        if not plates and image_bytes:
            try:
                from PIL import Image
                import io as _io

                img = Image.open(_io.BytesIO(image_bytes))
                img_info = {
                    "format": img.format,
                    "size": list(img.size),
                    "mode": img.mode,
                }

                # Attempt pytesseract if available
                try:
                    import pytesseract  # type: ignore[import]

                    # Preprocess: convert to grayscale for better OCR
                    gray = img.convert("L")
                    ocr_text = pytesseract.image_to_string(
                        gray,
                        config="--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789- ",
                    )
                    heuristic_matches = _guess_country_from_text(ocr_text)
                    plates.extend(heuristic_matches)
                    log.info("license_plate_decoder: OCR heuristic found matches", count=len(heuristic_matches))
                except ImportError:
                    log.info("license_plate_decoder: pytesseract not available, skipping OCR")

            except Exception as exc:
                log.warning("license_plate_decoder: Pillow processing failed", error=str(exc))
                img_info = {}

        extracted_identifiers: list[str] = []
        for p in plates:
            if p.get("plate_text"):
                extracted_identifiers.append(f"license_plate:{p['plate_text']}")
            if p.get("likely_country"):
                extracted_identifiers.append(f"country:{p['likely_country']}")

        return {
            "found": bool(plates),
            "image_url": input_value,
            "plate_count": len(plates),
            "plates": plates,
            "extracted_identifiers": list(set(extracted_identifiers)),
            "api_used": "platerecognizer" if api_key else "heuristic_ocr",
            "manual_tools": [
                "https://www.platerecognizer.com — commercial API with free tier",
                "https://www.carjam.co.nz — NZ/AU plate lookup",
                "https://www.regcheck.org.uk — UK plate check",
                "https://www.kennzeichenauskunft.de — German plate lookup",
            ],
            "educational_note": (
                "License plates follow national standards with distinct formats per country. "
                "AI-powered OCR (e.g., PlateRecognizer) achieves >96% accuracy. "
                "Always verify against national vehicle registries for legal investigations."
            ),
        }
