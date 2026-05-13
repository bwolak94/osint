"""Pydantic schemas for the LinkedIn Intel module."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

QueryType = Literal["username", "name"]


class LinkedInIntelRequest(BaseModel):
    query: str
    query_type: QueryType = "username"


class LinkedInProfileSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    username: str | None = None
    full_name: str | None = None
    headline: str | None = None
    location: str | None = None
    profile_pic_url: str | None = None
    profile_url: str | None = None
    connections: str | None = None
    company: str | None = None
    school: str | None = None
    source: str = "unknown"


class LinkedInIntelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    query: str
    query_type: str
    total_results: int
    results: list[LinkedInProfileSchema]
    created_at: datetime


class LinkedInIntelListResponse(BaseModel):
    items: list[LinkedInIntelResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
