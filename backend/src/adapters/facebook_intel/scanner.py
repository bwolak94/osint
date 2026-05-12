"""Facebook Intel scanner: gathers public profile data from Facebook."""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Literal

import httpx

QueryType = Literal["name", "username", "id", "email", "phone"]

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_GRAPH_BASE = "https://graph.facebook.com/v19.0"
_SEARCH_URL = "https://www.facebook.com/public/search/people/"


@dataclass
class FacebookProfile:
    uid: str | None
    name: str | None
    username: str | None
    profile_url: str | None
    avatar_url: str | None
    cover_url: str | None
    bio: str | None
    location: str | None
    hometown: str | None
    work: list[str]
    education: list[str]
    followers: int | None
    friends: int | None
    public_posts: int | None
    verified: bool
    category: str | None
    source: str


@dataclass
class FacebookIntelResult:
    query: str
    query_type: QueryType
    profiles: list[FacebookProfile] = field(default_factory=list)


class FacebookIntelScanner:
    """
    Searches for public Facebook profile information.

    Supports:
    - Name search via public people search
    - Direct profile lookup by username/ID via Graph API (public fields only)
    - Email/phone pivot via public search index
    """

    async def scan(self, query: str, query_type: QueryType = "name") -> FacebookIntelResult:
        result = FacebookIntelResult(query=query, query_type=query_type)

        tasks: list = []

        if query_type in ("username", "id"):
            tasks.append(self._lookup_profile_direct(query))
        elif query_type == "name":
            tasks.append(self._search_by_name(query))
        elif query_type in ("email", "phone"):
            tasks.append(self._search_by_contact(query, query_type))
        else:
            tasks.append(self._search_by_name(query))

        gathered = await asyncio.gather(*tasks, return_exceptions=True)
        for r in gathered:
            if isinstance(r, list):
                result.profiles.extend(r)

        return result

    # ------------------------------------------------------------------
    # Direct profile lookup by username or numeric ID
    # ------------------------------------------------------------------

    async def _lookup_profile_direct(self, identifier: str) -> list[FacebookProfile]:
        profiles: list[FacebookProfile] = []

        # Build URL — numeric IDs use ?id=, vanity names use path
        if identifier.isdigit():
            profile_url = f"https://www.facebook.com/profile.php?id={identifier}"
            graph_id = identifier
        else:
            profile_url = f"https://www.facebook.com/{identifier}"
            graph_id = identifier

        # Try Graph API (public fields only, no token required for some)
        gp = await self._fetch_graph_profile(graph_id)
        if gp:
            profiles.append(gp)
            return profiles

        # Fallback: scrape HTML page for Open Graph metadata
        scraped = await self._scrape_og_profile(profile_url, identifier)
        if scraped:
            profiles.append(scraped)

        return profiles

    async def _fetch_graph_profile(self, identifier: str) -> FacebookProfile | None:
        url = f"{_GRAPH_BASE}/{identifier}"
        fields = "id,name,about,location,hometown,work,education,picture,cover,fan_count,username,category,verification_status"
        try:
            async with httpx.AsyncClient(timeout=10.0, headers=_HEADERS, follow_redirects=True) as client:
                resp = await client.get(url, params={"fields": fields})
                if resp.status_code != 200:
                    return None
                data = resp.json()
                if "error" in data:
                    return None
        except Exception:
            return None

        uid = data.get("id")
        name = data.get("name")
        username = data.get("username")
        profile_url = f"https://www.facebook.com/{username or uid or identifier}"
        avatar_url: str | None = None
        cover_url: str | None = None

        pic = data.get("picture", {})
        if isinstance(pic, dict):
            pic_data = pic.get("data", {})
            avatar_url = pic_data.get("url") if isinstance(pic_data, dict) else None

        cover = data.get("cover", {})
        if isinstance(cover, dict):
            cover_url = cover.get("source")

        location = None
        loc = data.get("location", {})
        if isinstance(loc, dict):
            location = loc.get("name")

        hometown = None
        ht = data.get("hometown", {})
        if isinstance(ht, dict):
            hometown = ht.get("name")

        work: list[str] = []
        for w in (data.get("work") or []):
            if isinstance(w, dict):
                emp = w.get("employer", {})
                if isinstance(emp, dict) and emp.get("name"):
                    work.append(emp["name"])

        education: list[str] = []
        for e in (data.get("education") or []):
            if isinstance(e, dict):
                school = e.get("school", {})
                if isinstance(school, dict) and school.get("name"):
                    education.append(school["name"])

        return FacebookProfile(
            uid=uid,
            name=name,
            username=username,
            profile_url=profile_url,
            avatar_url=avatar_url,
            cover_url=cover_url,
            bio=data.get("about"),
            location=location,
            hometown=hometown,
            work=work,
            education=education,
            followers=data.get("fan_count"),
            friends=None,
            public_posts=None,
            verified=data.get("verification_status") == "blue_verified",
            category=data.get("category"),
            source="graph_api",
        )

    async def _scrape_og_profile(self, url: str, identifier: str) -> FacebookProfile | None:
        try:
            async with httpx.AsyncClient(timeout=10.0, headers=_HEADERS, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code not in (200, 301, 302):
                    return None
                html = resp.text
        except Exception:
            return None

        name = _og(html, "og:title") or _meta(html, "title")
        bio = _og(html, "og:description")
        avatar_url = _og(html, "og:image")
        profile_url = _og(html, "og:url") or url

        # Extract numeric ID from HTML if present
        uid_match = re.search(r'"userID":"(\d+)"', html) or re.search(r'entity_id=(\d+)', html)
        uid = uid_match.group(1) if uid_match else (identifier if identifier.isdigit() else None)

        if not name:
            return None

        return FacebookProfile(
            uid=uid,
            name=name,
            username=None if identifier.isdigit() else identifier,
            profile_url=profile_url,
            avatar_url=avatar_url,
            cover_url=None,
            bio=bio,
            location=None,
            hometown=None,
            work=[],
            education=[],
            followers=None,
            friends=None,
            public_posts=None,
            verified=False,
            category=None,
            source="html_scrape",
        )

    # ------------------------------------------------------------------
    # Public name search
    # ------------------------------------------------------------------

    async def _search_by_name(self, name: str) -> list[FacebookProfile]:
        """Use Facebook's public people search endpoint."""
        profiles: list[FacebookProfile] = []
        try:
            async with httpx.AsyncClient(timeout=10.0, headers=_HEADERS, follow_redirects=True) as client:
                resp = await client.get(_SEARCH_URL, params={"q": name})
                if resp.status_code not in (200,):
                    return profiles
                html = resp.text
        except Exception:
            return profiles

        # Extract profile cards from JSON-encoded props in the HTML
        uid_pattern = re.findall(r'"id":"(\d{10,})"[^}]*?"name":"([^"]+)"', html)
        seen: set[str] = set()
        for uid, pname in uid_pattern[:10]:
            if uid in seen:
                continue
            seen.add(uid)
            profiles.append(FacebookProfile(
                uid=uid,
                name=pname,
                username=None,
                profile_url=f"https://www.facebook.com/profile.php?id={uid}",
                avatar_url=None,
                cover_url=None,
                bio=None,
                location=None,
                hometown=None,
                work=[],
                education=[],
                followers=None,
                friends=None,
                public_posts=None,
                verified=False,
                category=None,
                source="people_search",
            ))

        return profiles

    # ------------------------------------------------------------------
    # Contact pivot (email / phone)
    # ------------------------------------------------------------------

    async def _search_by_contact(self, contact: str, contact_type: str) -> list[FacebookProfile]:
        """Attempt to find profiles linked to an email or phone via public search."""
        # Facebook's search index doesn't expose email/phone directly in public search.
        # We perform a name-style search with the identifier as keyword.
        return await self._search_by_name(contact)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _og(html: str, prop: str) -> str | None:
    m = re.search(rf'<meta\s+property="{re.escape(prop)}"\s+content="([^"]*)"', html)
    if not m:
        m = re.search(rf'<meta\s+content="([^"]*)"\s+property="{re.escape(prop)}"', html)
    return m.group(1) if m else None


def _meta(html: str, name: str) -> str | None:
    m = re.search(rf'<meta\s+name="{re.escape(name)}"\s+content="([^"]*)"', html)
    return m.group(1) if m else None
