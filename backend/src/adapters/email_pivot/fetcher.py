"""Email pivot — linked account discovery via free public APIs."""
from __future__ import annotations
import asyncio
import hashlib
from dataclasses import dataclass, field
import httpx


@dataclass
class LinkedAccount:
    platform: str
    profile_url: str | None = None
    display_name: str | None = None
    avatar_url: str | None = None
    exists: bool = True


@dataclass
class EmailInfo:
    email: str
    domain: str | None = None
    mx_records: list[str] = field(default_factory=list)
    gravatar_exists: bool = False
    gravatar_display_name: str | None = None
    gravatar_avatar_url: str | None = None
    gravatar_profile_url: str | None = None
    github_username: str | None = None
    github_profile_url: str | None = None
    hibp_breaches: list[str] = field(default_factory=list)
    hibp_checked: bool = False
    deliverable: bool | None = None
    disposable: bool = False
    linked_accounts: list[LinkedAccount] = field(default_factory=list)
    source: str = "email_pivot"


async def pivot_email(email: str, hibp_key: str = "") -> EmailInfo:
    email = email.strip().lower()
    domain = email.split("@")[-1] if "@" in email else None
    info = EmailInfo(email=email, domain=domain)

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        await asyncio.gather(
            _check_gravatar(client, email, info),
            _check_github(client, email, info),
            _check_hibp(client, email, info, hibp_key),
            _check_disposable(client, domain, info),
        )

    # Build linked accounts list
    if info.gravatar_exists:
        info.linked_accounts.append(
            LinkedAccount(
                platform="Gravatar",
                profile_url=info.gravatar_profile_url,
                display_name=info.gravatar_display_name,
                avatar_url=info.gravatar_avatar_url,
            )
        )
    if info.github_username:
        info.linked_accounts.append(
            LinkedAccount(
                platform="GitHub",
                profile_url=info.github_profile_url,
                display_name=info.github_username,
            )
        )

    return info


async def _check_gravatar(client: httpx.AsyncClient, email: str, info: EmailInfo) -> None:
    md5 = hashlib.md5(email.encode()).hexdigest()
    try:
        r = await client.get(f"https://www.gravatar.com/{md5}.json")
        if r.status_code == 200:
            data = r.json().get("entry", [{}])[0]
            info.gravatar_exists = True
            info.gravatar_display_name = data.get("displayName") or data.get("name", {}).get("formatted")
            info.gravatar_avatar_url = f"https://www.gravatar.com/avatar/{md5}?s=200"
            info.gravatar_profile_url = data.get("profileUrl") or f"https://www.gravatar.com/{md5}"
    except Exception:
        pass


async def _check_github(client: httpx.AsyncClient, email: str, info: EmailInfo) -> None:
    try:
        r = await client.get(
            "https://api.github.com/search/users",
            params={"q": f"{email} in:email", "per_page": 1},
            headers={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
        )
        if r.status_code == 200:
            items = r.json().get("items", [])
            if items:
                info.github_username = items[0].get("login")
                info.github_profile_url = items[0].get("html_url")
    except Exception:
        pass


async def _check_hibp(client: httpx.AsyncClient, email: str, info: EmailInfo, key: str) -> None:
    if not key:
        return
    try:
        r = await client.get(
            f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}",
            headers={"hibp-api-key": key, "User-Agent": "OSINT-Platform"},
            params={"truncateResponse": "true"},
        )
        info.hibp_checked = True
        if r.status_code == 200:
            info.hibp_breaches = [b.get("Name", "") for b in r.json()]
    except Exception:
        pass


async def _check_disposable(client: httpx.AsyncClient, domain: str | None, info: EmailInfo) -> None:
    if not domain:
        return
    try:
        r = await client.get(
            "https://open.kickbox.com/v1/disposable/" + domain,
        )
        if r.status_code == 200:
            info.disposable = r.json().get("disposable", False)
    except Exception:
        pass
