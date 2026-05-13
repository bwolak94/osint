"""Playwright-based LinkedIn profile scraper.

Uses Yahoo site:linkedin.com/in/ dork to discover profiles by name,
then scrapes public OG tags from each profile page.
Direct username lookup also supported.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote_plus

_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

_STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
window.chrome = { runtime: {} };
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
"""

_LI_SLUG_BLACKLIST = frozenset({
    "login", "signup", "feed", "jobs", "company", "school", "groups",
    "learning", "messaging", "notifications", "premium", "pub", "m",
    "help", "legal", "policies", "about", "comm",
})


@dataclass
class LiProfile:
    profile_id: str | None = None
    username: str | None = None
    full_name: str | None = None
    headline: str | None = None
    location: str | None = None
    profile_pic_url: str | None = None
    profile_url: str | None = None
    connections: str | None = None
    company: str | None = None
    school: str | None = None
    source: str = "playwright"


@dataclass
class LiScrapeResult:
    query: str
    query_type: str
    profiles: list[LiProfile] = field(default_factory=list)


async def scrape_linkedin(query: str, query_type: str) -> LiScrapeResult:
    from playwright.async_api import async_playwright

    result = LiScrapeResult(query=query, query_type=query_type)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
                  "--disable-blink-features=AutomationControlled"],
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

            if query_type == "username":
                profiles = await _lookup_profile(page, query)
            else:
                profiles = await _search_by_name(page, query)

            result.profiles = profiles
        finally:
            await ctx.close()
            await browser.close()

    return result


async def _lookup_profile(page: Any, username: str) -> list[LiProfile]:
    url = f"https://www.linkedin.com/in/{username}/"
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await _delay(page, 1.0, 2.0)
    except Exception:
        return []

    if "authwall" in page.url or "login" in page.url:
        # LinkedIn redirects unauth users to authwall — extract from OG tags
        pass

    return [p for p in [await _extract(page, username, url)] if p]


async def _extract(page: Any, username: str, url: str) -> LiProfile | None:
    og_title = await page.evaluate(
        "() => { const m = document.querySelector('meta[property=\"og:title\"]'); return m ? m.content : null; }"
    )
    og_desc = await page.evaluate(
        "() => { const m = document.querySelector('meta[property=\"og:description\"]'); return m ? m.content : null; }"
    )
    og_image = await page.evaluate(
        "() => { const m = document.querySelector('meta[property=\"og:image\"]'); return m ? m.content : null; }"
    )

    if not og_title or og_title.strip() in ("LinkedIn", ""):
        return None

    # "Full Name - Headline | LinkedIn" or "Full Name | LinkedIn"
    name_m = re.match(r'^(.+?)\s*[|\-]\s*(.+?)\s*(?:\|\s*LinkedIn)?$', og_title)
    full_name = name_m.group(1).strip() if name_m else og_title.replace("| LinkedIn", "").strip()
    headline = name_m.group(2).strip() if name_m else None
    if headline and headline.lower() == "linkedin":
        headline = None

    # OG description: "View Full Name's professional profile on LinkedIn..."
    # Sometimes contains location
    location = None
    if og_desc:
        loc_m = re.search(r'(?:located in|lives? in|based in)\s+([A-Z][^.]+)', og_desc, re.IGNORECASE)
        if loc_m:
            location = loc_m.group(1).strip()

    return LiProfile(
        username=username,
        full_name=full_name,
        headline=headline,
        location=location,
        profile_pic_url=og_image,
        profile_url=url,
        source="playwright_profile",
    )


async def _search_by_name(page: Any, query: str) -> list[LiProfile]:
    # Accept Yahoo GDPR consent
    try:
        await page.goto("https://yahoo.com", wait_until="domcontentloaded", timeout=15000)
        await _delay(page, 0.8, 1.5)
        btn = await page.query_selector('button[name="agree"]')
        if btn:
            await btn.click()
            await _delay(page, 0.5, 1.0)
    except Exception:
        pass

    search_query = f'site:linkedin.com/in/ "{query}"'
    yahoo_url = f"https://search.yahoo.com/search?p={quote_plus(search_query)}&n=10"

    try:
        await page.goto(yahoo_url, wait_until="domcontentloaded", timeout=20000)
        await _delay(page, 1.5, 2.0)
    except Exception:
        return []

    html = await page.content()
    raw = re.findall(r'href="https?://(?:www\.)?linkedin\.com/in/([a-zA-Z0-9._%-]+)', html)

    from urllib.parse import unquote
    seen: set[str] = set()
    slugs: list[str] = []
    for slug in raw:
        slug = unquote(slug.split("?")[0].rstrip("/")).split("/")[0]
        if slug and slug.lower() not in _LI_SLUG_BLACKLIST and slug not in seen:
            seen.add(slug)
            slugs.append(slug)

    profiles: list[LiProfile] = []
    for slug in slugs[:5]:
        url = f"https://www.linkedin.com/in/{slug}/"
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            await _delay(page, 0.8, 1.5)
        except Exception:
            continue
        p = await _extract(page, slug, url)
        if p:
            profiles.append(p)

    return profiles


async def _delay(page: Any, min_s: float = 1.0, max_s: float = 2.0) -> None:
    import asyncio, random
    await asyncio.sleep(random.uniform(min_s, max_s))
