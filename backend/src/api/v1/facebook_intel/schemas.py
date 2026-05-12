"""Pydantic schemas for the Facebook Intel module."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

QueryType = Literal["name", "username", "id", "email", "phone"]


class FacebookIntelRequest(BaseModel):
    query: str
    query_type: QueryType = "name"


class FacebookProfileSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uid: str | None = None
    name: str | None = None
    username: str | None = None
    profile_url: str | None = None
    avatar_url: str | None = None
    cover_url: str | None = None
    bio: str | None = None
    location: str | None = None
    hometown: str | None = None
    work: list[str] = []
    education: list[str] = []
    followers: int | None = None
    friends: int | None = None
    public_posts: int | None = None
    verified: bool = False
    category: str | None = None
    source: str = "unknown"


class FacebookIntelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    query: str
    query_type: str
    total_results: int
    results: list[FacebookProfileSchema]
    created_at: datetime


class FacebookIntelListResponse(BaseModel):
    items: list[FacebookIntelResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
