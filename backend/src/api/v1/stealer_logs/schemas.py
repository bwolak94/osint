"""Pydantic schemas for stealer log intelligence API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class InfectionSchema(BaseModel):
    source: str
    stealer_family: str | None = None
    date_compromised: str | None = None
    computer_name: str | None = None
    operating_system: str | None = None
    ip: str | None = None
    country: str | None = None
    credentials_count: int = 0
    cookies_count: int = 0
    autofill_count: int = 0
    has_crypto_wallet: bool = False
    risk_level: str = "unknown"
    raw: dict = {}
    error: str | None = None


class StealerLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    query: str
    query_type: str
    total_infections: int
    infections: list[InfectionSchema]
    sources_checked: list[str]
    created_at: datetime


class StealerLogListResponse(BaseModel):
    items: list[StealerLogResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class StealerLogRequest(BaseModel):
    query: str
    query_type: str  # email / domain / ip
