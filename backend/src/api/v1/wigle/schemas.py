"""Pydantic schemas for the WiGLE module."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class WigleRequest(BaseModel):
    query: str
    query_type: str  # 'bssid' or 'ssid'


class WigleNetworkSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    netid: str
    ssid: str | None = None
    encryption: str | None = None
    channel: int | None = None
    trilat: float | None = None
    trilong: float | None = None
    first_seen: str | None = None
    last_seen: str | None = None
    country: str | None = None
    region: str | None = None
    city: str | None = None
    maps_url: str | None = None


class WigleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    query: str
    query_type: str
    total_results: int
    results: list[WigleNetworkSchema]
    created_at: datetime


class WigleListResponse(BaseModel):
    items: list[WigleResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
