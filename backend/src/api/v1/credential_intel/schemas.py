"""Pydantic schemas for Credential Intelligence API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class CredentialIntelRequest(BaseModel):
    target: str
    # "email" | "domain" | "ip" | "hash"
    target_type: str = "email"
    modules: list[str] | None = None

    @field_validator("target")
    @classmethod
    def target_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("target must not be empty")
        return v

    @field_validator("target_type")
    @classmethod
    def valid_target_type(cls, v: str) -> str:
        allowed = {"email", "domain", "ip", "hash"}
        if v not in allowed:
            raise ValueError(f"target_type must be one of {allowed}")
        return v


class CredentialIntelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    target: str
    target_type: str
    modules_run: list[str]
    results: dict
    created_at: datetime


class CredentialIntelListResponse(BaseModel):
    items: list[CredentialIntelResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
