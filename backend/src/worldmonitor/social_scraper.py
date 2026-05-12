"""WorldMonitor social post scraper.

Sources:
1. Truth Social (Mastodon-compatible API) — Trump & White House accounts
2. X/Twitter via RSSHub public instances (best-effort, nitter fallback)
3. Official government press release RSS feeds (always-on political sources)

Stores to Redis:
    wm:posts:latest           — list[400] newest-first merged posts
    wm:posts:by_account:{id}  — list[50] per account
    wm:posts:meta             — JSON stats
"""

from __future__ import annotations

import asyncio
import json
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

import httpx
import redis.asyncio as aioredis
import structlog

from .cache import CACHE_TIERS, fnv1a_hash, redis_key
from .rss_aggregator import _extract_image, _parse_date

log = structlog.get_logger(__name__)

KEY_POSTS = redis_key("posts", "latest")
KEY_POSTS_META = redis_key("posts", "meta")
KEY_POSTS_BY_ACCOUNT = "wm:posts:by_account:{account_id}"

_FETCH_TIMEOUT = 12.0

# ── Truth Social ───────────────────────────────────────────────────────────────
# Maps account slug → (mastodon_id, display_name)
TRUTH_SOCIAL_ACCOUNTS: dict[str, tuple[str, str]] = {
    "realDonaldTrump": ("107780257626128497", "Donald Trump"),
    "TrumpWarRoom":    ("107785917173225913", "Trump War Room"),
}

# ── RSSHub instances for X/Twitter ────────────────────────────────────────────
RSSHUB_INSTANCES = [
    "https://rsshub.app",
    "https://rsshub.rssforever.com",
    "https://rsshub.be",
    "https://hub.slarker.me",
]

NITTER_INSTANCES = [
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.1d4.us",
    "https://nitter.kavin.rocks",
]

# X accounts to track: {handle: display_name}
X_ACCOUNTS: dict[str, str] = {
    "POTUS":           "White House",
    "StateDept":       "U.S. State Dept",
    "DeptofDefense":   "Pentagon",
    "NATO":            "NATO",
    "UN":              "United Nations",
    "ZelenskyyUa":     "Zelensky",
    "IsraeliPM":       "Israeli PM",
    "10DowningStreet": "UK Prime Minister",
    "EU_Commission":   "EU Commission",
    "JointStaff":      "Joint Chiefs",
    "MFA_Russia":      "Russia MFA",
    "SecBlinken":      "Secretary of State",
    "realDonaldTrump": "Donald Trump",
}

# ── Official government / political press release RSS feeds ───────────────────
# These are always-on, highly reliable political sources
OFFICIAL_FEEDS: list[dict[str, str]] = [
    # ── US Executive ──────────────────────────────────────────────────────────
    {"id": "whitehouse-news",    "name": "White House",            "url": "https://www.whitehouse.gov/feed/",                                                                       "account_id": "whitehouse"},
    {"id": "state-dept-press",   "name": "State Dept",             "url": "https://www.state.gov/press-releases/feed/",                                                             "account_id": "statedept"},
    {"id": "pentagon-news",      "name": "Pentagon",               "url": "https://www.defense.gov/DesktopModules/ArticleCS/RSS.ashx?ContentType=400&Site=945&max=10",              "account_id": "pentagon"},
    {"id": "trump-campaign",     "name": "Donald Trump",           "url": "https://www.donaldjtrump.com/feed",                                                                      "account_id": "trump_official"},
    {"id": "cia-news",           "name": "CIA News",               "url": "https://www.cia.gov/stories/feed/",                                                                      "account_id": "cia"},
    {"id": "dni-news",           "name": "DNI Press",              "url": "https://www.dni.gov/index.php/newsroom/press-releases?format=feed&type=rss",                             "account_id": "dni"},
    {"id": "dhs-news",           "name": "DHS News",               "url": "https://www.dhs.gov/dhs-news-releases-feed",                                                             "account_id": "dhs"},
    {"id": "nsc-news",           "name": "NSC / White House Security","url": "https://www.whitehouse.gov/national-security-council/feed/",                                         "account_id": "nsc"},
    # ── US Military / Intelligence ────────────────────────────────────────────
    {"id": "cisa-alerts",        "name": "CISA Alerts",            "url": "https://www.cisa.gov/cybersecurity-advisories/all.xml",                                                  "account_id": "cisa"},
    {"id": "us-army-news",       "name": "US Army News",           "url": "https://www.army.mil/rss/",                                                                              "account_id": "usarmy"},
    {"id": "us-navy-news",       "name": "US Navy News",           "url": "https://www.navy.mil/DesktopModules/ArticleCS/RSS.ashx?ContentType=400&Site=1&max=10",                  "account_id": "usnavy"},
    {"id": "us-airforce-news",   "name": "US Air Force",           "url": "https://www.af.mil/DesktopModules/ArticleCS/RSS.ashx?ContentType=400&Site=1&max=10",                    "account_id": "usairforce"},
    {"id": "joint-chiefs",       "name": "Joint Chiefs",           "url": "https://www.jcs.mil/DesktopModules/ArticleCS/RSS.ashx?ContentType=400&Site=1&max=10",                   "account_id": "jcs"},
    # ── US Congress ───────────────────────────────────────────────────────────
    {"id": "house-gop",          "name": "House Republicans",      "url": "https://www.speaker.gov/feed/",                                                                          "account_id": "housegop"},
    {"id": "senate-majority",    "name": "Senate GOP",             "url": "https://www.majorityleader.senate.gov/rss/news.xml",                                                     "account_id": "senatemajority"},
    {"id": "senate-foreign-rel", "name": "Senate Foreign Relations","url": "https://www.foreign.senate.gov/press/rss/",                                                            "account_id": "senateforeign"},
    # ── International Orgs ───────────────────────────────────────────────────
    {"id": "nato-press",         "name": "NATO",                   "url": "https://www.nato.int/cps/en/natohq/news.htm?selectedLocale=en&type=pressReleases&format=rss",            "account_id": "nato"},
    {"id": "un-sc",              "name": "UN Security Council",    "url": "https://news.un.org/feed/subscribe/en/news/topic/peace-and-security/rss.xml",                            "account_id": "unsc"},
    {"id": "un-general",         "name": "UN News",                "url": "https://news.un.org/feed/subscribe/en/news/rss.xml",                                                     "account_id": "un"},
    {"id": "eu-council",         "name": "EU Council",             "url": "https://www.consilium.europa.eu/en/press/press-releases/feed/",                                          "account_id": "eucouncil"},
    {"id": "eu-commission",      "name": "EU Commission",          "url": "https://ec.europa.eu/commission/presscorner/api/documents?service=feeds&type=ip&language=en&limit=10",   "account_id": "eucommission"},
    {"id": "iaea-news",          "name": "IAEA",                   "url": "https://www.iaea.org/newscenter/news/feed",                                                               "account_id": "iaea"},
    # ── Foreign Governments ───────────────────────────────────────────────────
    {"id": "kremlin-en",         "name": "Kremlin",                "url": "http://en.kremlin.ru/events/president/news/feed",                                                         "account_id": "kremlin"},
    {"id": "uk-gov-news",        "name": "UK Gov Foreign Policy",  "url": "https://www.gov.uk/government/organisations/foreign-commonwealth-development-office.atom",               "account_id": "ukfco"},
    {"id": "uk-mod-news",        "name": "UK Ministry of Defence", "url": "https://www.gov.uk/government/organisations/ministry-of-defence.atom",                                   "account_id": "ukmod"},
    {"id": "israel-pm",          "name": "Israel PM Office",       "url": "https://www.gov.il/api/MobileRSS/GetRSSById?LangID=2&NodeID=44",                                         "account_id": "israelpm"},
    {"id": "ukraine-mfa",        "name": "Ukraine MFA",            "url": "https://mfa.gov.ua/en/feed",                                                                             "account_id": "ukrainemfa"},
    {"id": "nato-allies-shape",  "name": "NATO SHAPE",             "url": "https://shape.nato.int/feed",                                                                            "account_id": "natoshape"},
]

NS_ATOM = "http://www.w3.org/2005/Atom"
NS_MEDIA = "http://search.yahoo.com/mrss/"


# ── Truth Social (Mastodon API) ────────────────────────────────────────────────

async def _fetch_truthsocial(
    client: httpx.AsyncClient,
    slug: str,
    mastodon_id: str,
    display_name: str,
) -> list[dict[str, Any]]:
    """Fetch posts via Truth Social's Mastodon-compatible statuses API."""
    url = f"https://truthsocial.com/api/v1/accounts/{mastodon_id}/statuses?limit=20"
    try:
        resp = await client.get(
            url,
            timeout=_FETCH_TIMEOUT,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; WorldMonitor/1.0)",
                "Accept": "application/json",
            },
            follow_redirects=True,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        log.warning("truthsocial_fetch_failed", account=slug, error=str(exc))
        return []

    if not isinstance(data, list):
        return []

    posts: list[dict[str, Any]] = []
    for status in data:
        content_html = status.get("content") or status.get("text") or ""
        # Strip HTML tags for title
        import re
        clean = re.sub(r"<[^>]+>", " ", content_html).strip()
        clean = re.sub(r"\s+", " ", clean)
        if not clean:
            continue

        post_url = status.get("url") or status.get("uri") or ""
        created_at = status.get("created_at") or ""

        # Extract image from media_attachments
        image_url = ""
        for att in status.get("media_attachments", []):
            if att.get("type") == "image":
                image_url = att.get("url") or att.get("preview_url") or ""
                break
        if not image_url:
            # Try card preview
            card = status.get("card") or {}
            image_url = card.get("image") or ""

        entry: dict[str, Any] = {
            "id": fnv1a_hash(f"ts_{slug}_{status.get('id', clean)}"),
            "title": clean[:200],
            "url": post_url,
            "description": clean[:800],
            "published_at": created_at or datetime.now(tz=timezone.utc).isoformat(),
            "source_id": f"ts_{slug}",
            "source_name": f"@{slug}",
            "display_name": display_name,
            "category": "social",
            "platform": "truthsocial",
            "account_id": slug,
            "country_iso": "US",
            "language": "en",
            "weight": 1.0,
        }
        if image_url:
            entry["image_url"] = image_url
        posts.append(entry)

    log.debug("truthsocial_fetched", account=slug, count=len(posts))
    return posts


# ── X / Twitter via RSSHub ────────────────────────────────────────────────────

def _parse_x_rss(content: bytes, handle: str, display_name: str) -> list[dict[str, Any]]:
    """Parse an RSS/Atom feed from RSSHub or nitter into post dicts."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return []

    tag = root.tag.lower()
    posts: list[dict[str, Any]] = []

    if "feed" in tag or NS_ATOM in tag:
        for entry in root.findall(f"{{{NS_ATOM}}}entry"):
            title_el = entry.find(f"{{{NS_ATOM}}}title")
            title = (title_el.text or "").strip() if title_el is not None else ""
            link_el = entry.find(f"{{{NS_ATOM}}}link")
            url = link_el.get("href", "") if link_el is not None else ""
            content_el = entry.find(f"{{{NS_ATOM}}}content") or entry.find(f"{{{NS_ATOM}}}summary")
            description = (content_el.text or "").strip()[:800] if content_el is not None else ""
            updated_el = entry.find(f"{{{NS_ATOM}}}updated") or entry.find(f"{{{NS_ATOM}}}published")
            pub_date = _parse_date((updated_el.text or "") if updated_el is not None else "")
            image_url = _extract_image(entry, description)
            if not title and not description:
                continue
            entry_dict: dict[str, Any] = {
                "id": fnv1a_hash(f"x_{handle}_{title}_{pub_date}"),
                "title": title or description[:120],
                "url": url,
                "description": description,
                "published_at": pub_date,
                "source_id": f"x_{handle}",
                "source_name": f"@{handle}",
                "display_name": display_name,
                "category": "social",
                "platform": "x",
                "account_id": handle,
                "country_iso": "US",
                "language": "en",
                "weight": 1.0,
            }
            if image_url:
                entry_dict["image_url"] = image_url
            posts.append(entry_dict)
    else:
        channel = root.find("channel")
        if channel is not None:
            for item in channel.findall("item"):
                title = (item.findtext("title") or "").strip()
                url = (item.findtext("link") or "").strip()
                description = (item.findtext("description") or "").strip()[:800]
                pub_date = _parse_date(item.findtext("pubDate") or "")
                image_url = _extract_image(item, description)
                if not title and not description:
                    continue
                item_dict: dict[str, Any] = {
                    "id": fnv1a_hash(f"x_{handle}_{title}_{pub_date}"),
                    "title": title or description[:120],
                    "url": url,
                    "description": description,
                    "published_at": pub_date,
                    "source_id": f"x_{handle}",
                    "source_name": f"@{handle}",
                    "display_name": display_name,
                    "category": "social",
                    "platform": "x",
                    "account_id": handle,
                    "country_iso": "US",
                    "language": "en",
                    "weight": 1.0,
                }
                if image_url:
                    item_dict["image_url"] = image_url
                posts.append(item_dict)

    return posts


async def _fetch_x_account(
    client: httpx.AsyncClient,
    handle: str,
    display_name: str,
) -> list[dict[str, Any]]:
    """Try self-hosted RSSHub, then public RSSHub instances, then nitter."""
    import os
    self_hosted = os.getenv("RSSHUB_SELF_HOSTED_URL", "").strip().rstrip("/")
    instances = ([self_hosted] if self_hosted else []) + RSSHUB_INSTANCES

    # Try RSSHub first
    for instance in instances:
        url = f"{instance}/twitter/user/{handle}"
        try:
            resp = await client.get(
                url, timeout=_FETCH_TIMEOUT,
                headers={"User-Agent": "Mozilla/5.0 (compatible; WorldMonitor/1.0)"},
                follow_redirects=True,
            )
            if resp.status_code == 200 and len(resp.content) > 300:
                posts = _parse_x_rss(resp.content, handle, display_name)
                if posts:
                    log.debug("x_rsshub_fetched", handle=handle, instance=instance, count=len(posts))
                    return posts
        except Exception:
            continue

    # Fallback: nitter
    for instance in NITTER_INSTANCES:
        url = f"{instance}/{handle}/rss"
        try:
            resp = await client.get(
                url, timeout=_FETCH_TIMEOUT,
                headers={"User-Agent": "Mozilla/5.0 (compatible; WorldMonitor/1.0)"},
                follow_redirects=True,
            )
            if resp.status_code == 200 and len(resp.content) > 300:
                posts = _parse_x_rss(resp.content, handle, display_name)
                if posts:
                    log.debug("x_nitter_fetched", handle=handle, instance=instance, count=len(posts))
                    return posts
        except Exception:
            continue

    log.warning("x_account_all_sources_failed", handle=handle)
    return []


# ── Official government press release RSS ─────────────────────────────────────

def _parse_official_rss(content: bytes, feed: dict[str, str]) -> list[dict[str, Any]]:
    """Parse an official government RSS into post-style dicts."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return []

    posts: list[dict[str, Any]] = []
    channel = root.find("channel")
    entries = channel.findall("item") if channel is not None else []

    # Also try Atom
    if not entries:
        entries = root.findall(f"{{{NS_ATOM}}}entry")

    for item in entries:
        title = (item.findtext("title") or item.findtext(f"{{{NS_ATOM}}}title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not link:
            link_el = item.find(f"{{{NS_ATOM}}}link")
            link = link_el.get("href", "") if link_el is not None else ""
        description = (item.findtext("description") or item.findtext(f"{{{NS_ATOM}}}summary") or "").strip()[:800]
        pub_raw = item.findtext("pubDate") or item.findtext(f"{{{NS_ATOM}}}updated") or ""
        pub_date = _parse_date(pub_raw)
        image_url = _extract_image(item, description)

        if not title:
            continue

        entry: dict[str, Any] = {
            "id": fnv1a_hash(f"official_{feed['account_id']}_{title}_{pub_date}"),
            "title": title,
            "url": link,
            "description": description,
            "published_at": pub_date,
            "source_id": feed["id"],
            "source_name": feed["name"],
            "display_name": feed["name"],
            "category": "social",
            "platform": "official",
            "account_id": feed["account_id"],
            "country_iso": "US",
            "language": "en",
            "weight": 0.9,
        }
        if image_url:
            entry["image_url"] = image_url
        posts.append(entry)

    return posts


async def _fetch_official_feed(
    client: httpx.AsyncClient,
    feed: dict[str, str],
) -> list[dict[str, Any]]:
    try:
        resp = await client.get(
            feed["url"], timeout=_FETCH_TIMEOUT,
            headers={"User-Agent": "WorldMonitor/1.0"},
            follow_redirects=True,
        )
        if resp.status_code == 200:
            posts = _parse_official_rss(resp.content, feed)
            log.debug("official_feed_fetched", feed=feed["id"], count=len(posts))
            return posts
    except Exception as exc:
        log.warning("official_feed_failed", feed=feed["id"], error=str(exc))
    return []


# ── Main aggregation ──────────────────────────────────────────────────────────

async def run_social_aggregation(redis: aioredis.Redis) -> dict[str, Any]:
    """Fetch all social sources and persist to Redis."""
    started_at = time.time()

    async with httpx.AsyncClient() as client:
        ts_tasks = [
            _fetch_truthsocial(client, slug, mid, name)
            for slug, (mid, name) in TRUTH_SOCIAL_ACCOUNTS.items()
        ]
        # X/Twitter scraping via RSSHub/nitter — only attempt if a self-hosted
        # RSSHub instance is configured via RSSHUB_SELF_HOSTED_URL env var,
        # otherwise all public instances are consistently unavailable.
        import os
        self_hosted = os.getenv("RSSHUB_SELF_HOSTED_URL", "").strip()
        x_tasks = (
            [_fetch_x_account(client, handle, name) for handle, name in X_ACCOUNTS.items()]
            if self_hosted
            else []
        )
        official_tasks = [
            _fetch_official_feed(client, feed)
            for feed in OFFICIAL_FEEDS
        ]
        results = await asyncio.gather(*ts_tasks, *x_tasks, *official_tasks, return_exceptions=True)

    all_posts: list[dict[str, Any]] = []
    account_counts: dict[str, int] = {}

    for result in results:
        if isinstance(result, Exception):
            log.error("social_task_error", error=str(result))
            continue
        for post in result:  # type: ignore[union-attr]
            acct = post.get("account_id", "unknown")
            account_counts[acct] = account_counts.get(acct, 0) + 1
        all_posts.extend(result)  # type: ignore[arg-type]

    # Deduplicate by id
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for p in all_posts:
        if p["id"] not in seen:
            seen.add(p["id"])
            unique.append(p)

    unique.sort(key=lambda x: x.get("published_at", ""), reverse=True)

    # Persist
    pipe = redis.pipeline()
    pipe.delete(KEY_POSTS)
    for post in unique[:400]:
        pipe.rpush(KEY_POSTS, json.dumps(post, default=str))
    pipe.expire(KEY_POSTS, 172800)

    by_account: dict[str, list[dict[str, Any]]] = {}
    for p in unique:
        by_account.setdefault(p["account_id"], []).append(p)
    for acct_id, posts in by_account.items():
        key = KEY_POSTS_BY_ACCOUNT.format(account_id=acct_id)
        pipe.delete(key)
        for p in posts[:50]:
            pipe.rpush(key, json.dumps(p, default=str))
        pipe.expire(key, 172800)

    meta: dict[str, Any] = {
        "last_run": datetime.now(tz=timezone.utc).isoformat(),
        "duration_s": round(time.time() - started_at, 2),
        "total_posts": len(unique),
        "account_counts": account_counts,
    }
    pipe.setex(KEY_POSTS_META, CACHE_TIERS["fast"] * 4, json.dumps(meta))
    await pipe.execute()

    log.info("social_aggregation_complete", total=len(unique), sources_with_data=len([v for v in account_counts.values() if v > 0]))
    return meta
