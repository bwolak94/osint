"""Pydantic schemas for Tech Recon API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class TechReconRequest(BaseModel):
    target: str
    modules: list[str] | None = None  # None = run all applicable modules

    @field_validator("target")
    @classmethod
    def target_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("target must not be empty")
        return v


class ModuleResult(BaseModel):
    module: str
    found: bool
    data: dict
    error: str | None = None


class TechReconResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    target: str
    target_type: str
    modules_run: list[str]
    results: dict
    created_at: datetime


class TechReconListResponse(BaseModel):
    items: list[TechReconResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
