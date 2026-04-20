"""Visual Landmark Match — uses Google Cloud Vision API to identify real-world landmarks in an image URL."""
import base64
import os
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_VISION_API_ENDPOINT = "https://vision.googleapis.com/v1/images:annotate"


class VisualLandmarkMatchScanner(BaseOsintScanner):
    """Identifies geographic landmarks in an image via Google Cloud Vision LANDMARK_DETECTION."""

    scanner_name = "visual_landmark_match"
    supported_input_types = frozenset({ScanInputType.URL})
    cache_ttl = 86400

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        api_key = os.getenv("GOOGLE_VISION_API_KEY")

        if not api_key:
            return {
                "found": False,
                "image_url": input_value,
                "error": "GOOGLE_VISION_API_KEY not configured",
                "manual_alternatives": [
                    "Upload the image to https://lens.google.com for visual landmark search",
                    "Use https://www.geospy.ai for AI-powered geolocation from photos",
                    "Try https://suncalc.org with shadow analysis for rough geolocation",
                ],
                "educational_note": (
                    "Google Cloud Vision LANDMARK_DETECTION identifies famous places, monuments, and geographic "
                    "features in images. It returns name, score, and GPS coordinates of detected landmarks."
                ),
            }

        # First, fetch the image bytes to send as base64 (avoids URL access issues on private images)
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                img_resp = await client.get(input_value, headers={"User-Agent": "Mozilla/5.0"})
                img_resp.raise_for_status()
                image_b64 = base64.b64encode(img_resp.content).decode("utf-8")
        except Exception as exc:
            return {"found": False, "image_url": input_value, "error": f"Failed to fetch image: {exc}"}

        payload = {
            "requests": [
                {
                    "image": {"content": image_b64},
                    "features": [
                        {"type": "LANDMARK_DETECTION", "maxResults": 10},
                        {"type": "WEB_DETECTION", "maxResults": 5},
                    ],
                }
            ]
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{_VISION_API_ENDPOINT}?key={api_key}",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            return {"found": False, "error": f"Vision API HTTP error {exc.response.status_code}: {exc.response.text}"}
        except Exception as exc:
            return {"found": False, "error": f"Vision API request failed: {exc}"}

        response_annotations = data.get("responses", [{}])[0]

        # Parse landmark annotations
        landmarks: list[dict[str, Any]] = []
        for ann in response_annotations.get("landmarkAnnotations", []):
            locations = ann.get("locations", [])
            coords: dict[str, float] | None = None
            if locations:
                ll = locations[0].get("latLng", {})
                coords = {
                    "latitude": ll.get("latitude"),
                    "longitude": ll.get("longitude"),
                }
            landmarks.append({
                "name": ann.get("description"),
                "score": round(ann.get("score", 0.0), 4),
                "coordinates": coords,
                "bounding_poly": [
                    {"x": v.get("x"), "y": v.get("y")}
                    for v in ann.get("boundingPoly", {}).get("vertices", [])
                ],
            })

        # Parse web detection for additional context
        web_entities: list[dict[str, Any]] = []
        for entity in response_annotations.get("webDetection", {}).get("webEntities", [])[:5]:
            web_entities.append({
                "entity_id": entity.get("entityId"),
                "description": entity.get("description"),
                "score": round(entity.get("score", 0.0), 4),
            })

        extracted_identifiers: list[str] = []
        for lm in landmarks:
            if lm.get("coordinates"):
                c = lm["coordinates"]
                extracted_identifiers.append(f"coordinates:{c['latitude']},{c['longitude']}")

        return {
            "found": bool(landmarks),
            "image_url": input_value,
            "landmark_count": len(landmarks),
            "landmarks": landmarks,
            "web_entities": web_entities,
            "top_landmark": landmarks[0] if landmarks else None,
            "extracted_identifiers": extracted_identifiers,
            "educational_note": (
                "Landmark detection can pinpoint exact locations from tourist photos, event images, or "
                "street-level photography. High-confidence matches (>0.85) are typically reliable for geolocation."
            ),
        }
