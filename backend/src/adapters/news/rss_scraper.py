"""RSS feed scraper — fetches and normalises articles from multiple news sources.

Supports RSS 2.0 and Atom 1.0 feeds. Uses httpx for async HTTP.
No external RSS parsing library required — ElementTree handles both formats.
"""
from __future__ import annotations

import asyncio
import re
import uuid
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

log = structlog.get_logger(__name__)

# Default news sources — mix of general, tech, and security feeds
DEFAULT_FEED_URLS: list[str] = [
    "https://feeds.bbci.co.uk/news/rss.xml",              # BBC World
    "https://feeds.reuters.com/reuters/topNews",           # Reuters Top News
    "https://news.ycombinator.com/rss",                   # Hacker News
    "https://techcrunch.com/feed/",                        # TechCrunch
    "https://www.theregister.com/headlines.atom",          # The Register
    "https://feeds.feedburner.com/TheHackersNews",         # The Hacker News (security)
    "https://www.bleepingcomputer.com/feed/",              # BleepingComputer
    "https://krebsonsecurity.com/feed/",                   # Krebs on Security
    "https://www.wired.com/feed/rss",                      # Wired
    "https://arstechnica.com/feed/",                       # Ars Technica
    "https://www.darkreading.com/rss.xml",                 # Dark Reading
    "https://www.securityweek.com/feed/",                  # SecurityWeek
    "https://www.zdnet.com/news/rss.xml",                  # ZDNet
    "https://feeds.a.dj.com/rss/RSSWorldNews.xml",        # WSJ World
    "https://rss.cnn.com/rss/edition.rss",                 # CNN World
]

_ATOM_NS = "http://www.w3.org/2005/Atom"
_TIMEOUT = 10.0


def _extract_domain(url: str) -> str:
    """Extract the domain from a URL, stripping the leading www. prefix."""
    try:
        return urlparse(url).netloc.lstrip("www.")
    except Exception:
        return ""


def _strip_html(text: str) -> str:
    """Remove HTML tags and normalise whitespace."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text)).strip()


def _parse_rss(root: ET.Element, feed_url: str) -> list[dict[str, Any]]:
    """Parse an RSS 2.0 feed and return a list of raw article dicts."""
    articles: list[dict[str, Any]] = []
    channel = root.find("channel")
    if channel is None:
        return articles

    for item in channel.findall("item"):
        title = (item.findtext("title") or "").strip()
        url = (item.findtext("link") or "").strip()
        raw_content = item.findtext("description") or ""
        content = _strip_html(raw_content)[:2000]
        pub_raw = item.findtext("pubDate") or ""

        articles.append({
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, url or str(uuid.uuid4()))),
            "url": url,
            "title": title,
            "content": content,
            "summary": "",
            "published_at": pub_raw,
            "source_domain": _extract_domain(url) or _extract_domain(feed_url),
            "credibility_score": 0.0,
            "is_duplicate": False,
            "tags": [],
            "relevance_score": 0.5,
            "action_relevance_score": 0.0,
            "critique_score": 0.0,
            "image_url": "",
        })
    return articles


def _parse_atom(root: ET.Element, feed_url: str) -> list[dict[str, Any]]:
    """Parse an Atom 1.0 feed and return a list of raw article dicts."""
    articles: list[dict[str, Any]] = []
    ns = {"atom": _ATOM_NS}

    for entry in root.findall("atom:entry", ns):
        title = (entry.findtext("atom:title", namespaces=ns) or "").strip()

        # Prefer rel=alternate link, fall back to first link element
        link_el = entry.find("atom:link[@rel='alternate']", ns) or entry.find("atom:link", ns)
        url = (link_el.get("href", "") if link_el is not None else "").strip()

        content_el = entry.find("atom:content", ns) or entry.find("atom:summary", ns)
        raw_content = (content_el.text or "") if content_el is not None else ""
        content = _strip_html(raw_content)[:2000]

        pub_raw = (
            entry.findtext("atom:updated", namespaces=ns)
            or entry.findtext("atom:published", namespaces=ns)
            or ""
        )

        articles.append({
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, url or str(uuid.uuid4()))),
            "url": url,
            "title": title,
            "content": content,
            "summary": "",
            "published_at": pub_raw,
            "source_domain": _extract_domain(url) or _extract_domain(feed_url),
            "credibility_score": 0.0,
            "is_duplicate": False,
            "tags": [],
            "relevance_score": 0.5,
            "action_relevance_score": 0.0,
            "critique_score": 0.0,
            "image_url": "",
        })
    return articles


async def fetch_feed(client: httpx.AsyncClient, feed_url: str) -> list[dict[str, Any]]:
    """Fetch and parse a single RSS/Atom feed. Returns [] on any error."""
    try:
        resp = await client.get(feed_url, timeout=_TIMEOUT, follow_redirects=True)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        tag = root.tag.lower()

        if "rss" in tag:
            return _parse_rss(root, feed_url)
        if "feed" in tag or _ATOM_NS in root.tag:
            return _parse_atom(root, feed_url)

        # Unknown root tag — try RSS first, then Atom
        articles = _parse_rss(root, feed_url)
        if not articles:
            articles = _parse_atom(root, feed_url)
        return articles

    except Exception as exc:
        log.warning("rss_fetch_error", url=feed_url, error=str(exc))
        return []


async def scrape_all_feeds(
    feed_urls: list[str] | None = None,
    concurrency: int = 5,
) -> list[dict[str, Any]]:
    """Fetch all configured feeds concurrently and return a deduplicated article list.

    Args:
        feed_urls:   Override the default feed list. Defaults to DEFAULT_FEED_URLS.
        concurrency: Max simultaneous HTTP connections.

    Returns:
        Deduplicated (by URL) list of raw article dicts.
    """
    urls = feed_urls or DEFAULT_FEED_URLS
    semaphore = asyncio.Semaphore(concurrency)
    headers = {"User-Agent": "Mozilla/5.0 (compatible; OSINTBot/1.0)"}

    async with httpx.AsyncClient(headers=headers) as client:

        async def _bounded_fetch(url: str) -> list[dict[str, Any]]:
            async with semaphore:
                return await fetch_feed(client, url)

        results = await asyncio.gather(*[_bounded_fetch(u) for u in urls])

    # Flatten and dedup by URL
    seen_urls: set[str] = set()
    merged: list[dict[str, Any]] = []
    for batch in results:
        for article in batch:
            if article["url"] and article["url"] not in seen_urls:
                seen_urls.add(article["url"])
                merged.append(article)

    log.info("rss_scrape_complete", total_articles=len(merged), feeds=len(urls))
    return merged
