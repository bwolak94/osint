"""Pydantic schemas for the GitHub Intel module."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

QueryType = Literal["username", "name", "email"]


class GitHubIntelRequest(BaseModel):
    query: str
    query_type: QueryType = "username"


class GhRepoSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    description: str | None = None
    stars: int = 0
    forks: int = 0
    language: str | None = None
    url: str = ""
    is_fork: bool = False
    topics: list[str] = []


class GitHubProfileSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int | None = None
    username: str | None = None
    full_name: str | None = None
    bio: str | None = None
    avatar_url: str | None = None
    profile_url: str | None = None
    company: str | None = None
    blog: str | None = None
    location: str | None = None
    email: str | None = None
    twitter_username: str | None = None
    followers: int | None = None
    following: int | None = None
    public_repos: int | None = None
    public_gists: int | None = None
    created_at: str | None = None
    is_verified: bool = False
    account_type: str = "User"
    top_repos: list[GhRepoSchema] = []
    languages: list[str] = []
    emails_in_commits: list[str] = []
    source: str = "github_api"


class GitHubIntelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    query: str
    query_type: str
    total_results: int
    results: list[GitHubProfileSchema]
    created_at: datetime


class GitHubIntelListResponse(BaseModel):
    items: list[GitHubIntelResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
