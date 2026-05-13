"""GitHub OSINT fetcher using the public GitHub API.

No token required for basic lookups (60 req/hour).
Set GITHUB_API_TOKEN in config for 5000 req/hour.
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

_BASE = "https://api.github.com"
_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "OSINT-Platform/1.0",
}


@dataclass
class GhRepo:
    name: str
    description: str | None
    stars: int
    forks: int
    language: str | None
    url: str
    is_fork: bool
    topics: list[str] = field(default_factory=list)


@dataclass
class GhProfile:
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
    top_repos: list[GhRepo] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    emails_in_commits: list[str] = field(default_factory=list)
    source: str = "github_api"


@dataclass
class GhScrapeResult:
    query: str
    query_type: str
    profiles: list[GhProfile] = field(default_factory=list)


async def fetch_github(query: str, query_type: str, token: str = "") -> GhScrapeResult:
    result = GhScrapeResult(query=query, query_type=query_type)
    headers = dict(_HEADERS)
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(headers=headers, timeout=15.0, follow_redirects=True) as client:
        if query_type in ("username", "id"):
            profile = await _fetch_user(client, query)
            if profile:
                result.profiles = [profile]
        else:
            result.profiles = await _search_users(client, query)

    return result


async def _fetch_user(client: httpx.AsyncClient, username: str) -> GhProfile | None:
    try:
        r = await client.get(f"{_BASE}/users/{username}")
        if r.status_code != 200:
            return None
        data = r.json()
    except Exception:
        return None

    profile = GhProfile(
        user_id=data.get("id"),
        username=data.get("login"),
        full_name=data.get("name"),
        bio=data.get("bio"),
        avatar_url=data.get("avatar_url"),
        profile_url=data.get("html_url"),
        company=data.get("company"),
        blog=data.get("blog") or None,
        location=data.get("location"),
        email=data.get("email"),
        twitter_username=data.get("twitter_username"),
        followers=data.get("followers"),
        following=data.get("following"),
        public_repos=data.get("public_repos"),
        public_gists=data.get("public_gists"),
        created_at=data.get("created_at"),
        account_type=data.get("type", "User"),
    )

    # Fetch top repos
    try:
        repos_r = await client.get(
            f"{_BASE}/users/{username}/repos",
            params={"sort": "stars", "per_page": 10, "type": "owner"},
        )
        if repos_r.status_code == 200:
            repos_data = repos_r.json()
            profile.top_repos = [
                GhRepo(
                    name=repo["name"],
                    description=repo.get("description"),
                    stars=repo.get("stargazers_count", 0),
                    forks=repo.get("forks_count", 0),
                    language=repo.get("language"),
                    url=repo.get("html_url", ""),
                    is_fork=repo.get("fork", False),
                    topics=repo.get("topics", []),
                )
                for repo in repos_data
                if not repo.get("fork", False)
            ]
            profile.languages = list({
                r.language for r in profile.top_repos if r.language
            })
    except Exception:
        pass

    # Try to find emails exposed in recent commit events
    try:
        events_r = await client.get(
            f"{_BASE}/users/{username}/events/public", params={"per_page": 30}
        )
        if events_r.status_code == 200:
            emails: set[str] = set()
            for event in events_r.json():
                if event.get("type") == "PushEvent":
                    for commit in event.get("payload", {}).get("commits", []):
                        author_email = commit.get("author", {}).get("email", "")
                        if author_email and not author_email.endswith(
                            ("noreply.github.com", "users.noreply.github.com")
                        ):
                            emails.add(author_email)
            profile.emails_in_commits = list(emails)[:10]
    except Exception:
        pass

    return profile


async def _search_users(client: httpx.AsyncClient, query: str) -> list[GhProfile]:
    try:
        r = await client.get(
            f"{_BASE}/search/users",
            params={"q": query, "per_page": 5, "sort": "followers"},
        )
        if r.status_code != 200:
            return []
        items = r.json().get("items", [])
    except Exception:
        return []

    profiles: list[GhProfile] = []
    for item in items[:5]:
        await asyncio.sleep(0.3)  # respect rate limits
        profile = await _fetch_user(client, item["login"])
        if profile:
            profiles.append(profile)

    return profiles
