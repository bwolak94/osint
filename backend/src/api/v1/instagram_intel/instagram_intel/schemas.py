"""Pydantic schemas for the Instagram Intel module."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

QueryType = Literal["username", "name", "id"]


class InstagramIntelRequest(BaseModel):
    query: str
    query_type: QueryType = "username"


class InstagramProfileSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str | None = None
    username: str | None = None
    full_name: str | None = None
    biography: str | None = None
    profile_pic_url: str | None = None
    profile_url: str | None = None
    follower_count: int | None = None
    following_count: int | None = None
    media_count: int | None = None
    is_verified: bool = False
    is_private: bool = False
    external_url: str | None = None
    category: str | None = None
    source: str = "unknown"


class InstagramIntelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    query: str
    query_type: str
    total_results: int
    results: list[InstagramProfileSchema]
    created_at: datetime


class InstagramIntelListResponse(BaseModel):
    items: list[InstagramIntelResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
