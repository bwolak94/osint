"""Playwright-based Instagram profile scraper.

Supports:
- Public profile lookup by username (www.instagram.com/{username}/)
- Public people search by name via Yahoo site:instagram.com dork

Uses OG tags + embedded JSON blobs for data extraction.
Works without credentials for public profiles.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote_plus

_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

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

_IG_SLUG_BLACKLIST = frozenset({
    "login", "accounts", "explore", "reels", "stories", "direct",
    "p", "tv", "reel", "static", "legal", "about", "help",
    "privacy", "safety", "press", "api", "graphql", "data",
    "web", "embed", "share", "badges",
})


@dataclass
class IgProfile:
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
    source: str = "playwright"


@dataclass
class IgScrapeResult:
    query: str
    query_type: str
    profiles: list[IgProfile] = field(default_factory=list)


async def scrape_instagram(query: str, query_type: str) -> IgScrapeResult:
    """Entry point: scrape Instagram via Playwright."""
    from playwright.async_api import async_playwright

    result = IgScrapeResult(query=query, query_type=query_type)

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
            user_agent=_USER_AGENT,
            viewport={"width": 1280, "height": 900},
            locale="en-US",
            timezone_id="America/New_York",
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        await ctx.add_init_script(_STEALTH_JS)

        try:
            page = await ctx.new_page()
            await page.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf}", lambda r: r.abort())

            if query_type in ("username", "id"):
                profiles = await _lookup_profile(page, query)
            else:
                # name / email / phone — search via Yahoo dork
                profiles = await _search_by_name(page, query)

            result.profiles = profiles
        finally:
            await ctx.close()
            await browser.close()

    return result


# ---------------------------------------------------------------------------
# Direct profile lookup by username
# ---------------------------------------------------------------------------

async def _lookup_profile(page: Any, username: str) -> list[IgProfile]:
    url = f"https://www.instagram.com/{username}/"
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await _human_delay(page, 1.0, 2.0)
    except Exception:
        return []

    final_url = page.url
    if "login" in final_url or "accounts" in final_url:
        return []

    profile = await _extract_profile(page, username)
    return [profile] if profile else []


async def _extract_profile(page: Any, username: str) -> IgProfile | None:
    html = await page.content()

    # OG title format: "Full Name (@username) • Instagram photos and videos"
    og_title = await page.evaluate(
        "() => { const m = document.querySelector('meta[property=\"og:title\"]'); return m ? m.content : null; }"
    )
    # OG description: "X Followers, Y Following, Z Posts — See Instagram..."
    og_desc = await page.evaluate(
        "() => { const m = document.querySelector('meta[property=\"og:description\"]'); return m ? m.content : null; }"
    )
    og_image = await page.evaluate(
        "() => { const m = document.querySelector('meta[property=\"og:image\"]'); return m ? m.content : null; }"
    )

    if not og_title:
        return None

    # Parse full name and username from OG title
    # "Full Name (@username) • Instagram photos and videos"
    name_m = re.match(r'^(.+?)\s*\(@([^)]+)\)', og_title or "")
    full_name = name_m.group(1).strip() if name_m else None
    ig_username = name_m.group(2).strip() if name_m else username

    # Parse counts from OG description
    # "1,234 Followers, 567 Following, 89 Posts"
    follower_count = None
    following_count = None
    media_count = None
    if og_desc:
        f_m = re.search(r'([\d,]+)\s+Followers?', og_desc, re.IGNORECASE)
        if f_m:
            follower_count = _parse_count(f_m.group(1))
        fo_m = re.search(r'([\d,]+)\s+Following', og_desc, re.IGNORECASE)
        if fo_m:
            following_count = _parse_count(fo_m.group(1))
        p_m = re.search(r'([\d,]+)\s+Posts?', og_desc, re.IGNORECASE)
        if p_m:
            media_count = _parse_count(p_m.group(1))

    # Try to extract from embedded JSON blobs
    user_id = _re_first(r'"id"\s*:\s*"(\d{5,})"', html)
    biography = _re_first(r'"biography"\s*:\s*"([^"]{0,500})"', html)
    is_verified = bool(re.search(r'"is_verified"\s*:\s*true', html))
    is_private = bool(re.search(r'"is_private"\s*:\s*true', html))
    external_url = _re_first(r'"external_url"\s*:\s*"([^"]+)"', html)
    category = _re_first(r'"category_name"\s*:\s*"([^"]+)"', html)

    # Fallback counts from JSON if OG didn't have them
    if follower_count is None:
        fc = _re_first(r'"follower_count"\s*:\s*(\d+)', html)
        follower_count = int(fc) if fc else None
    if following_count is None:
        fc = _re_first(r'"following_count"\s*:\s*(\d+)', html)
        following_count = int(fc) if fc else None
    if media_count is None:
        mc = _re_first(r'"media_count"\s*:\s*(\d+)', html)
        media_count = int(mc) if mc else None

    # biography from OG description if JSON didn't have it
    if not biography and og_desc:
        # Remove the counts prefix
        bio_m = re.sub(r'^[\d,\s]+(Followers?|Following|Posts?)[,\s]*', '', og_desc, flags=re.IGNORECASE)
        bio_m = re.sub(r'—\s*See Instagram.+$', '', bio_m, flags=re.IGNORECASE).strip()
        if bio_m and len(bio_m) > 5:
            biography = bio_m

    profile_url = f"https://www.instagram.com/{ig_username}/"

    return IgProfile(
        user_id=user_id,
        username=ig_username,
        full_name=full_name,
        biography=biography,
        profile_pic_url=og_image,
        profile_url=profile_url,
        follower_count=follower_count,
        following_count=following_count,
        media_count=media_count,
        is_verified=is_verified,
        is_private=is_private,
        external_url=external_url,
        category=category,
        source="playwright_profile",
    )


# ---------------------------------------------------------------------------
# Name search via Yahoo site:instagram.com dork
# ---------------------------------------------------------------------------

async def _search_by_name(page: Any, query: str) -> list[IgProfile]:
    ig_urls = await _yahoo_instagram_search(page, query)
    if not ig_urls:
        return []

    profiles: list[IgProfile] = []
    for url, slug in ig_urls[:5]:
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            await _human_delay(page, 0.8, 1.5)
        except Exception:
            continue

        final_url = page.url
        if "login" in final_url or "accounts" in final_url:
            continue

        profile = await _extract_profile(page, slug)
        if profile:
            profiles.append(profile)

    return profiles


async def _yahoo_instagram_search(page: Any, query: str) -> list[tuple[str, str]]:
    """Return list of (instagram_url, username) via Yahoo site:instagram.com dork."""
    # Accept GDPR consent if shown (EU IPs always get the consent wall first)
    try:
        await page.goto("https://yahoo.com", wait_until="domcontentloaded", timeout=15000)
        await _human_delay(page, 0.8, 1.5)
        btn = await page.query_selector('button[name="agree"]')
        if btn:
            await btn.click()
            await _human_delay(page, 0.5, 1.0)
    except Exception:
        pass

    search_query = f'site:instagram.com "{query}"'
    yahoo_url = f"https://search.yahoo.com/search?p={quote_plus(search_query)}&n=10"

    try:
        await page.goto(yahoo_url, wait_until="domcontentloaded", timeout=20000)
        await _human_delay(page, 1.5, 2.0)
    except Exception:
        return []

    html = await page.content()

    # Yahoo embeds raw Instagram URLs in href="https://www.instagram.com/{username}/..."
    raw_slugs = re.findall(
        r'href="https?://(?:www\.)?instagram\.com/([a-zA-Z0-9._%-]+)',
        html,
    )

    seen: set[str] = set()
    results: list[tuple[str, str]] = []
    for slug in raw_slugs:
        from urllib.parse import unquote
        slug = unquote(slug.split("?")[0].rstrip("/"))
        slug = slug.split("/")[0]
        if not slug or slug.lower() in _IG_SLUG_BLACKLIST:
            continue
        if slug in seen:
            continue
        seen.add(slug)
        results.append((f"https://www.instagram.com/{slug}/", slug))

    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _human_delay(page: Any, min_s: float = 1.0, max_s: float = 2.5) -> None:
    import asyncio
    import random
    await asyncio.sleep(random.uniform(min_s, max_s))


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
