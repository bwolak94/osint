from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel


class SubdomainTakeoverRequest(BaseModel):
    domain: str


class SubdomainResultSchema(BaseModel):
    subdomain: str
    cname: str | None = None
    vulnerable_service: str | None = None
    risk: str = "low"
    resolves: bool = True
    note: str | None = None


class SubdomainTakeoverResponse(BaseModel):
    id: uuid.UUID | None = None
    created_at: datetime | None = None
    domain: str
    total_subdomains: int
    vulnerable: list[SubdomainResultSchema] = []
    safe: list[SubdomainResultSchema] = []


class SubdomainTakeoverListResponse(BaseModel):
    items: list[SubdomainTakeoverResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
