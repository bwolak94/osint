"""Pydantic schemas for the Fediverse scanner module."""
from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class FediverseRequest(BaseModel):
    query: str


class FediverseProfileSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    platform: str
    handle: str
    display_name: str | None = None
    bio: str | None = None
    followers: int | None = None
    following: int | None = None
    posts: int | None = None
    did: str | None = None
    instance: str | None = None
    avatar_url: str | None = None
    profile_url: str | None = None
    created_at: str | None = None


class FediverseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    query: str
    total_results: int
    platforms_searched: list[str]
    results: list[FediverseProfileSchema]
    created_at: datetime


class FediverseListResponse(BaseModel):
    items: list[FediverseResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
