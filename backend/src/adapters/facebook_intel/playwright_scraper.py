"""Playwright-based Facebook profile scraper.

Supports:
- Public profile / page lookup by username or numeric ID (www.facebook.com)
- Public people search by name via Bing site:facebook.com dork
- Email / phone pivot via the same Bing search path

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
from urllib.parse import quote_plus

_DESKTOP_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

_USER_AGENTS = [
    _DESKTOP_UA,
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
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

# Facebook profile slugs that are navigation / utility pages, not real profiles
_FB_SLUG_BLACKLIST = frozenset({
    "login", "home", "share", "about", "help", "policies", "legal",
    "settings", "privacy", "groups", "events", "marketplace", "watch",
    "gaming", "pages", "search", "hashtag", "sharer", "dialog",
    "plugins", "photo", "photos", "video", "videos", "stories", "notes",
    "profile.php", "permalink.php", "l.php",
})


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
            viewport={"width": 1280, "height": 900},
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
                profiles = await _search_by_name(page, query)
            else:
                # email / phone: search as keyword
                profiles = await _search_by_name(page, query)

            result.profiles = profiles
        finally:
            await ctx.close()
            await browser.close()

    return result


# ---------------------------------------------------------------------------
# Direct profile lookup by username / numeric ID
# ---------------------------------------------------------------------------

async def _lookup_profile(page: Any, identifier: str) -> list[FbProfile]:
    """Fetch a public Facebook profile directly from www.facebook.com."""
    if identifier.isdigit():
        url = f"https://www.facebook.com/profile.php?id={identifier}"
    else:
        url = f"https://www.facebook.com/{identifier}"

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await _human_delay(page, 1.0, 2.0)
    except Exception:
        return []

    final_url = page.url

    # Redirected to login → profile is private or doesn't exist
    if "login" in final_url or "checkpoint" in final_url:
        return []

    profile = await _extract_profile(page, final_url, identifier)
    return [profile] if profile else []


async def _extract_profile(page: Any, url: str, identifier: str) -> FbProfile | None:
    """Extract profile data from the current page using OG tags + JSON blobs."""
    html = await page.content()

    name = await _og_or_title(page)
    if not name:
        return None

    # Numeric UID from embedded JSON
    uid_m = (
        re.search(r'"userID"\s*:\s*"(\d+)"', html)
        or re.search(r'"actorID"\s*:\s*"(\d+)"', html)
        or re.search(r'entity_id=(\d+)', html)
    )
    uid = uid_m.group(1) if uid_m else (identifier if identifier.isdigit() else None)

    username = None if identifier.isdigit() else identifier

    og_image = await page.evaluate(
        "() => { const m = document.querySelector('meta[property=\"og:image\"]'); return m ? m.content : null; }"
    )
    og_desc = await page.evaluate(
        "() => { const m = document.querySelector('meta[property=\"og:description\"]'); return m ? m.content : null; }"
    )

    location = _re_first(r'"location"\s*:\s*\{"name"\s*:\s*"([^"]+)"', html)
    hometown = _re_first(r'"hometown"\s*:\s*\{"name"\s*:\s*"([^"]+)"', html)
    work: list[str] = re.findall(r'"employer"\s*:\s*\{"name"\s*:\s*"([^"]+)"', html)[:5]
    education: list[str] = re.findall(r'"school"\s*:\s*\{"name"\s*:\s*"([^"]+)"', html)[:5]

    # Follower count — OG description often contains "X likes · Y talking"
    followers = None
    if og_desc:
        m = re.search(r'([\d,]+)\s+(?:likes?|followers?)', og_desc)
        if m:
            followers = _parse_count(m.group(1))
    if followers is None:
        followers = _parse_count(
            _re_first(r'"fan_count"\s*:\s*(\d+)', html)
            or _re_first(r'([\d,.]+[KkMm]?)\s+(?:followers|people follow)', html)
        )

    friends = _parse_count(_re_first(r'([\d,.]+[KkMm]?)\s+friends', html))
    verified = bool(re.search(r'"is_verified"\s*:\s*true', html))
    category = _re_first(r'"category"\s*:\s*"([^"]+)"', html)

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
        verified=verified,
        category=category,
        source="playwright_profile",
    )


# ---------------------------------------------------------------------------
# Name / contact search via Bing site:facebook.com dork
# ---------------------------------------------------------------------------

async def _search_by_name(page: Any, query: str) -> list[FbProfile]:
    """Find Facebook profiles via a Bing site:facebook.com search, then scrape each."""
    fb_urls = await _bing_facebook_search(page, query)
    if not fb_urls:
        return []

    profiles: list[FbProfile] = []
    for url, slug in fb_urls[:5]:  # cap at 5 to stay within task timeout
        profile = await _scrape_profile_url(page, url, slug)
        if profile:
            profiles.append(profile)

    return profiles


async def _bing_facebook_search(page: Any, query: str) -> list[tuple[str, str]]:
    """Return list of (facebook_url, slug) from Yahoo site:facebook.com results.

    Bing is blocked from Docker/datacenter IPs via CAPTCHA; Yahoo works reliably.
    GDPR consent is handled by visiting the Yahoo homepage first and clicking agree.
    """
    # Accept GDPR consent if shown (EU IPs always see the consent wall)
    try:
        await page.goto("https://yahoo.com", wait_until="domcontentloaded", timeout=15000)
        await _human_delay(page, 0.8, 1.5)
        btn = await page.query_selector('button[name="agree"]')
        if btn:
            await btn.click()
            await _human_delay(page, 0.5, 1.0)
    except Exception:
        pass  # Consent wall not present or navigation failed — proceed anyway

    search_query = f'site:facebook.com "{query}"'
    yahoo_url = f"https://search.yahoo.com/search?p={quote_plus(search_query)}&n=10"

    try:
        await page.goto(yahoo_url, wait_until="domcontentloaded", timeout=20000)
        await _human_delay(page, 1.5, 2.0)
    except Exception:
        return []

    html = await page.content()

    # Extract facebook.com profile slugs directly from href attributes.
    # Yahoo embeds raw FB URLs in href="https://www.facebook.com/{slug}/..."
    raw_urls = re.findall(
        r'href="https?://(?:www\.)?facebook\.com/([a-zA-Z0-9._%-]+)',
        html,
    )

    seen: set[str] = set()
    results: list[tuple[str, str]] = []
    for slug in raw_urls:
        # Decode percent-encoding, keep only the first path segment (the profile slug)
        from urllib.parse import unquote
        slug = unquote(slug.split("?")[0].rstrip("/"))
        # Strip sub-paths (videos/posts/watch/etc.) — take only first segment
        slug = slug.split("/")[0]
        if not slug or slug.lower() in _FB_SLUG_BLACKLIST:
            continue
        if slug in seen:
            continue
        seen.add(slug)
        results.append((f"https://www.facebook.com/{slug}", slug))

    return results


async def _scrape_profile_url(page: Any, url: str, slug: str) -> FbProfile | None:
    """Navigate to a Facebook profile URL and extract data."""
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await _human_delay(page, 0.8, 1.5)
    except Exception:
        return None

    final_url = page.url
    if "login" in final_url or "checkpoint" in final_url:
        return None

    return await _extract_profile(page, final_url, slug)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _og_or_title(page: Any) -> str | None:
    val = await page.evaluate(
        "() => {"
        "  const og = document.querySelector('meta[property=\"og:title\"]');"
        "  if (og && og.content) return og.content;"
        "  return document.title || null;"
        "}"
    )
    if not val:
        return None
    # Strip common suffixes like "| Facebook"
    return re.sub(r"\s*[|–-]\s*Facebook\s*$", "", val, flags=re.IGNORECASE).strip() or None


async def _human_delay(page: Any, min_s: float = 1.0, max_s: float = 2.5) -> None:
    import asyncio
    import random as _r
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
