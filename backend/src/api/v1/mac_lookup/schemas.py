"""Pydantic schemas for MAC address lookup API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class MacLookupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    mac_address: str
    oui_prefix: str | None
    manufacturer: str | None
    manufacturer_country: str | None
    device_type: str | None
    is_private: bool | None
    is_multicast: bool | None
    raw_data: dict
    created_at: datetime


class MacLookupListResponse(BaseModel):
    items: list[MacLookupResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class MacLookupRequest(BaseModel):
    mac_address: str
