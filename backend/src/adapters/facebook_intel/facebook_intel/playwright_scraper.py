"""Playwright-based Facebook profile scraper.

Supports:
- Public profile / page lookup by username or numeric ID (m.facebook.com)
- Public people search by name (facebook.com/public/search/people/)
- Email / phone pivot via the search index

Uses stealth mode to reduce bot detection. Works without credentials
for public profiles and pages. When FB_SESSION_COOKIES env var is set
(JSON array of cookie dicts exported from a logged-in browser), the
session is injected so private-profile data becomes available.
"""
from __future__ import annotations

import json
import os
import random
import re
from dataclasses import dataclass, field
from typing import Any

_USER_AGENTS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

_STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
window.chrome = { runtime: {} };
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
const _origQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (p) =>
    p.name === 'notifications'
        ? Promise.resolve({ state: Notification.permission })
        : _origQuery(p);
"""


@dataclass
class FbProfile:
    uid: str | None = None
    name: str | None = None
    username: str | None = None
    profile_url: str | None = None
    avatar_url: str | None = None
    cover_url: str | None = None
    bio: str | None = None
    location: str | None = None
    hometown: str | None = None
    work: list[str] = field(default_factory=list)
    education: list[str] = field(default_factory=list)
    followers: int | None = None
    friends: int | None = None
    public_posts: int | None = None
    verified: bool = False
    category: str | None = None
    source: str = "playwright"


@dataclass
class FbScrapeResult:
    query: str
    query_type: str
    profiles: list[FbProfile] = field(default_factory=list)


async def scrape_facebook(query: str, query_type: str) -> FbScrapeResult:
    """Entry point: scrape Facebook via Playwright."""
    from playwright.async_api import async_playwright

    result = FbScrapeResult(query=query, query_type=query_type)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        ctx = await browser.new_context(
            user_agent=random.choice(_USER_AGENTS),
            viewport={"width": 390, "height": 844},  # mobile viewport
            locale="en-US",
            timezone_id="America/New_York",
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        await ctx.add_init_script(_STEALTH_JS)

        # Inject saved session cookies if provided
        session_cookies = _load_session_cookies()
        if session_cookies:
            await ctx.add_cookies(session_cookies)

        try:
            page = await ctx.new_page()
            # Block images / fonts to speed up scraping
            await page.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf}", lambda r: r.abort())

            if query_type in ("username", "id"):
                profiles = await _lookup_profile(page, query)
            elif query_type == "name":
                profiles = await _search_people(page, query)
            else:
                # email / phone: use as search keyword
                profiles = await _search_people(page, query)

            result.profiles = profiles
        finally:
            await ctx.close()
            await browser.close()

    return result


# ---------------------------------------------------------------------------
# Direct profile lookup
# ---------------------------------------------------------------------------

async def _lookup_profile(page: Any, identifier: str) -> list[FbProfile]:
    # Try mobile site first — simpler markup, less JS required
    if identifier.isdigit():
        url = f"https://m.facebook.com/profile.php?id={identifier}"
    else:
        url = f"https://m.facebook.com/{identifier}"

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await _human_delay(page)
    except Exception:
        return []

    final_url = page.url

    # If we were redirected to login, profile is private or doesn't exist
    if "login" in final_url or "checkpoint" in final_url:
        return []

    profile = await _extract_mobile_profile(page, final_url, identifier)
    return [profile] if profile else []


async def _extract_mobile_profile(page: Any, url: str, identifier: str) -> FbProfile | None:
    html = await page.content()

    name = await _og_or_title(page)
    if not name:
        return None

    # Extract numeric UID
    uid_m = re.search(r'"userID"\s*:\s*"(\d+)"', html) \
        or re.search(r'entity_id=(\d+)', html) \
        or re.search(r'"owner"\s*:\s*\{"__typename"[^}]*"id"\s*:\s*"(\d+)"', html)
    uid = uid_m.group(1) if uid_m else (identifier if identifier.isdigit() else None)

    username = None if identifier.isdigit() else identifier

    # Avatar
    og_image = await page.evaluate(
        "() => { const m = document.querySelector('meta[property=\"og:image\"]'); return m ? m.content : null; }"
    )

    # Bio / description
    og_desc = await page.evaluate(
        "() => { const m = document.querySelector('meta[property=\"og:description\"]'); return m ? m.content : null; }"
    )

    # Location, work, education from structured data blocks
    location = _re_first(r'"location"\s*:\s*\{"name"\s*:\s*"([^"]+)"', html)
    hometown = _re_first(r'"hometown"\s*:\s*\{"name"\s*:\s*"([^"]+)"', html)

    work: list[str] = re.findall(r'"employer"\s*:\s*\{"name"\s*:\s*"([^"]+)"', html)[:5]
    education: list[str] = re.findall(r'"school"\s*:\s*\{"name"\s*:\s*"([^"]+)"', html)[:5]

    # Follower / friend counts
    followers = _parse_count(_re_first(r'([\d,.]+[KkMm]?)\s+(?:followers|people follow)', html))
    friends = _parse_count(_re_first(r'([\d,.]+[KkMm]?)\s+friends', html))

    verified_m = re.search(r'"is_verified"\s*:\s*(true)', html)

    return FbProfile(
        uid=uid,
        name=name,
        username=username,
        profile_url=url,
        avatar_url=og_image,
        bio=og_desc,
        location=location,
        hometown=hometown,
        work=work,
        education=education,
        followers=followers,
        friends=friends,
        verified=bool(verified_m),
        source="playwright_profile",
    )


# ---------------------------------------------------------------------------
# People search
# ---------------------------------------------------------------------------

async def _search_people(page: Any, query: str) -> list[FbProfile]:
    url = f"https://www.facebook.com/public/search/people/?q={query}"
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await _human_delay(page)
    except Exception:
        return []

    if "login" in page.url or "checkpoint" in page.url:
        # Try the mobile search as fallback
        return await _search_people_mobile(page, query)

    # Scroll down a bit to trigger lazy loading
    await page.evaluate("window.scrollTo(0, 800)")
    await _human_delay(page, 0.5, 1.5)

    html = await page.content()
    profiles = _parse_search_results_html(html, query)
    return profiles


async def _search_people_mobile(page: Any, query: str) -> list[FbProfile]:
    url = f"https://m.facebook.com/search/people/?q={query}"
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await _human_delay(page)
    except Exception:
        return []

    if "login" in page.url:
        return []

    html = await page.content()
    return _parse_search_results_html(html, query)


def _parse_search_results_html(html: str, query: str) -> list[FbProfile]:
    profiles: list[FbProfile] = []
    seen: set[str] = set()

    # Pattern 1: JSON-encoded profile cards in __data or __bbox
    for m in re.finditer(r'"id"\s*:\s*"(\d{8,})"[^}]{0,300}"name"\s*:\s*"([^"]+)"', html):
        uid, name = m.group(1), m.group(2)
        if uid in seen or len(name) < 2:
            continue
        seen.add(uid)
        avatar = _re_first(
            rf'"id"\s*:\s*"{re.escape(uid)}"[^{{}}]{{0,500}}"uri"\s*:\s*"([^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"',
            html,
        )
        profiles.append(FbProfile(
            uid=uid,
            name=name,
            profile_url=f"https://www.facebook.com/profile.php?id={uid}",
            avatar_url=avatar,
            source="playwright_search",
        ))
        if len(profiles) >= 10:
            break

    # Pattern 2: HTML profile links (mobile)
    if not profiles:
        for m in re.finditer(
            r'href="https?://(?:www\.|m\.)?facebook\.com/([^?"]+)\??\S*"[^>]*>([^<]{2,60})</a',
            html,
        ):
            slug, name = m.group(1), m.group(2).strip()
            if slug in ("login", "home", "share", "about", "search") or slug in seen:
                continue
            if len(name) < 2:
                continue
            seen.add(slug)
            profiles.append(FbProfile(
                name=name,
                username=slug,
                profile_url=f"https://www.facebook.com/{slug}",
                source="playwright_search_html",
            ))
            if len(profiles) >= 10:
                break

    return profiles


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _og_or_title(page: Any) -> str | None:
    val = await page.evaluate(
        "() => {"
        "  const og = document.querySelector('meta[property=\"og:title\"]');"
        "  if (og) return og.content;"
        "  return document.title || null;"
        "}"
    )
    if not val:
        return None
    # Strip common suffixes like "| Facebook"
    return re.sub(r"\s*[|–-]\s*Facebook\s*$", "", val, flags=re.IGNORECASE).strip() or None


async def _human_delay(page: Any, min_s: float = 1.0, max_s: float = 2.5) -> None:
    import asyncio, random as _r
    await asyncio.sleep(_r.uniform(min_s, max_s))


def _re_first(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text)
    return m.group(1) if m else None


def _parse_count(s: str | None) -> int | None:
    if not s:
        return None
    s = s.replace(",", "").strip()
    mult = 1
    if s.upper().endswith("K"):
        mult, s = 1_000, s[:-1]
    elif s.upper().endswith("M"):
        mult, s = 1_000_000, s[:-1]
    try:
        return int(float(s) * mult)
    except ValueError:
        return None


def _load_session_cookies() -> list[dict[str, Any]]:
    """Load Facebook session cookies from FB_SESSION_COOKIES env var (JSON array)."""
    raw = os.environ.get("FB_SESSION_COOKIES", "")
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []
