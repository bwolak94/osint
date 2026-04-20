"""Fediverse scanner: searches Bluesky (AT Protocol) and Mastodon instances."""
from __future__ import annotations
import asyncio
import httpx
from dataclasses import dataclass, field


@dataclass
class FediverseProfile:
    platform: str
    handle: str
    display_name: str | None
    bio: str | None
    followers: int | None
    following: int | None
    posts: int | None
    did: str | None  # Bluesky DID
    instance: str | None  # Mastodon instance
    avatar_url: str | None
    profile_url: str | None
    created_at: str | None


@dataclass
class FediverseResult:
    query: str
    profiles: list[FediverseProfile] = field(default_factory=list)
    platforms_searched: list[str] = field(default_factory=list)


MASTODON_INSTANCES = [
    "mastodon.social",
    "fosstodon.org",
    "hachyderm.io",
    "infosec.exchange",
]


class FediverseScanner:
    async def scan(self, query: str) -> FediverseResult:
        result = FediverseResult(query=query)
        tasks = [
            self._search_bluesky(query),
            *[self._search_mastodon(instance, query) for instance in MASTODON_INSTANCES],
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, list):
                result.profiles.extend(r)
        result.platforms_searched = ["bluesky"] + [f"mastodon:{i}" for i in MASTODON_INSTANCES]
        return result

    async def _search_bluesky(self, query: str) -> list[FediverseProfile]:
        url = "https://public.api.bsky.app/xrpc/app.bsky.actor.searchActors"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, params={"q": query, "limit": 10})
                resp.raise_for_status()
                data = resp.json()
        except Exception:
            return []
        profiles = []
        for actor in data.get("actors", []):
            profiles.append(FediverseProfile(
                platform="bluesky",
                handle=actor.get("handle", ""),
                display_name=actor.get("displayName"),
                bio=actor.get("description"),
                followers=actor.get("followersCount"),
                following=actor.get("followsCount"),
                posts=actor.get("postsCount"),
                did=actor.get("did"),
                instance=None,
                avatar_url=actor.get("avatar"),
                profile_url=f"https://bsky.app/profile/{actor.get('handle', '')}",
                created_at=actor.get("createdAt"),
            ))
        return profiles

    async def _search_mastodon(self, instance: str, query: str) -> list[FediverseProfile]:
        url = f"https://{instance}/api/v2/search"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, params={"q": query, "type": "accounts", "limit": 5})
                resp.raise_for_status()
                data = resp.json()
        except Exception:
            return []
        profiles = []
        for acct in data.get("accounts", []):
            profiles.append(FediverseProfile(
                platform="mastodon",
                handle=f"{acct.get('acct', '')}@{instance}",
                display_name=acct.get("display_name"),
                bio=acct.get("note"),
                followers=acct.get("followers_count"),
                following=acct.get("following_count"),
                posts=acct.get("statuses_count"),
                did=None,
                instance=instance,
                avatar_url=acct.get("avatar"),
                profile_url=acct.get("url"),
                created_at=acct.get("created_at"),
            ))
        return profiles
