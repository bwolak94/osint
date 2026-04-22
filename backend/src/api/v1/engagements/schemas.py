"""Pydantic schemas for engagement and target endpoints."""

from __future__ import annotations

import ipaddress
from datetime import datetime
from typing import List, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ScopeRulesSchema(BaseModel):
    allowed_cidrs: List[str] = Field(default_factory=list)
    allowed_domains: List[str] = Field(default_factory=list)
    excluded: List[str] = Field(default_factory=list)

    @field_validator("allowed_cidrs", mode="before")
    @classmethod
    def _validate_cidrs(cls, v: list[str]) -> list[str]:
        for cidr in v:
            try:
                ipaddress.ip_network(cidr, strict=False)
            except ValueError as exc:
                raise ValueError(f"Invalid CIDR {cidr!r}: {exc}") from exc
        return v


class CreateEngagementRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    client_name: str = Field(..., min_length=1, max_length=255)
    scope_rules: ScopeRulesSchema
    start_at: datetime | None = None
    expires_at: datetime | None = None


class EngagementResponse(BaseModel):
    id: UUID
    created_by: UUID
    name: str
    client_name: str
    roe_hash: str | None
    scope_rules: dict
    start_at: datetime | None
    expires_at: datetime | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class UpdateEngagementRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    client_name: str | None = Field(default=None, min_length=1, max_length=255)
    scope_rules: ScopeRulesSchema | None = None
    start_at: datetime | None = None
    expires_at: datetime | None = None
    status: Literal["active", "expired", "cancelled"] | None = None


class AddTargetRequest(BaseModel):
    type: Literal["ip", "cidr", "domain", "url"]
    value: str = Field(..., min_length=1)


class TargetResponse(BaseModel):
    id: UUID
    engagement_id: UUID
    type: str
    value: str
    validated_at: datetime | None
    metadata: dict

    model_config = {"from_attributes": True}


class ScopeValidateRequest(BaseModel):
    value: str = Field(..., description="IP, CIDR, domain, or URL to validate against scope.")
    type: Literal["ip", "cidr", "domain", "url"]


class ScopeValidateResponse(BaseModel):
    valid: bool
    reason: str | None = None


class PaginatedEngagementsResponse(BaseModel):
    items: List[EngagementResponse]
    total: int
    limit: int
    offset: int
