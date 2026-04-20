"""Pydantic schemas for email header analysis API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class HopSchema(BaseModel):
    index: int
    from_host: str | None
    by_host: str | None
    ip: str | None
    timestamp: str | None
    protocol: str | None
    delay_seconds: int | None


class EmailHeaderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    subject: str | None
    sender_from: str | None
    sender_reply_to: str | None
    originating_ip: str | None
    originating_country: str | None
    originating_city: str | None
    spf_result: str | None
    dkim_result: str | None
    dmarc_result: str | None
    is_spoofed: bool
    hops: list[HopSchema]
    raw_headers_summary: dict
    created_at: datetime


class EmailHeaderListResponse(BaseModel):
    items: list[EmailHeaderResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class EmailHeaderSubmit(BaseModel):
    raw_headers: str
