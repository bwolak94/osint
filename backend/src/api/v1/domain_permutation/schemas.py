"""Pydantic schemas for domain permutation API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PermutationItemSchema(BaseModel):
    fuzzer: str
    domain: str
    registered: bool
    dns_a: list[str]
    dns_mx: list[str]


class DomainPermutationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    target_domain: str
    total_permutations: int
    registered_count: int
    permutations: list[PermutationItemSchema]
    created_at: datetime


class DomainPermutationListResponse(BaseModel):
    items: list[DomainPermutationResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class DomainPermutationRequest(BaseModel):
    domain: str
