"""Pydantic schemas for the image checker API."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class GPSDataSchema(BaseModel):
    latitude: float
    longitude: float
    altitude: float | None = None
    gps_timestamp: str | None = None
    maps_url: str


class ImageCheckResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    file_hash: str
    file_size: int
    mime_type: str
    metadata: dict[str, Any]
    gps_data: GPSDataSchema | None
    camera_make: str | None
    camera_model: str | None
    taken_at: datetime | None
    created_at: datetime

    @field_validator("metadata", mode="before")
    @classmethod
    def sanitise_metadata(cls, v: Any) -> dict[str, Any]:
        """Ensure the metadata dict is JSON-safe (remove NaN/Inf floats)."""
        if not isinstance(v, dict):
            return {}
        return _sanitise_dict(v)


class ImageCheckListResponse(BaseModel):
    items: list[ImageCheckResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sanitise_dict(d: dict[str, Any]) -> dict[str, Any]:
    """Recursively replace NaN/Inf float values with None so they are
    serialisable to JSON."""
    result: dict[str, Any] = {}
    for k, v in d.items():
        result[k] = _sanitise_value(v)
    return result


def _sanitise_value(v: Any) -> Any:
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if isinstance(v, dict):
        return _sanitise_dict(v)
    if isinstance(v, list):
        return [_sanitise_value(i) for i in v]
    return v
