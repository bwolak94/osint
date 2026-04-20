"""Pydantic schemas for supply chain API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID
from typing import Any

from pydantic import BaseModel, ConfigDict


class CveSchema(BaseModel):
    id: str | None
    summary: str
    severity: str
    published: str | None


class PackageSchema(BaseModel):
    name: str
    registry: str
    version: str | None
    downloads: int | None
    maintainer_emails: list[str]
    cves: list[CveSchema]
    cve_count: int
    risk_score: str


class SupplyChainResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    target: str
    target_type: str
    total_packages: int
    total_cves: int
    packages: list[PackageSchema]
    created_at: datetime


class SupplyChainListResponse(BaseModel):
    items: list[SupplyChainResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class SupplyChainRequest(BaseModel):
    target: str
    target_type: str  # domain/github_user/github_org
