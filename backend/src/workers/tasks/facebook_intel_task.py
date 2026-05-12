"""Celery task: Facebook Intel Playwright scrape (heavy queue)."""
from __future__ import annotations

import asyncio
from typing import Any

import structlog

from src.workers.celery_app import celery_app

log = structlog.get_logger(__name__)


@celery_app.task(
    bind=True,
    name="facebook_intel.scrape",
    queue="heavy",
    max_retries=2,
    default_retry_delay=30,
    soft_time_limit=60,
    time_limit=90,
)
def facebook_intel_scrape_task(self: Any, query: str, query_type: str) -> dict[str, Any]:
    """Run a Playwright-based Facebook Intel scrape.

    Returns serialised list of profile dicts so the router can store them.
    """
    try:
        from src.adapters.facebook_intel.playwright_scraper import scrape_facebook

        result = asyncio.run(scrape_facebook(query, query_type))

        profiles_json = [
            {
                "uid": p.uid,
                "name": p.name,
                "username": p.username,
                "profile_url": p.profile_url,
                "avatar_url": p.avatar_url,
                "cover_url": p.cover_url,
                "bio": p.bio,
                "location": p.location,
                "hometown": p.hometown,
                "work": p.work,
                "education": p.education,
                "followers": p.followers,
                "friends": p.friends,
                "public_posts": p.public_posts,
                "verified": p.verified,
                "category": p.category,
                "source": p.source,
            }
            for p in result.profiles
        ]

        log.info("facebook_intel_task_done", query=query, count=len(profiles_json))
        return {"profiles": profiles_json, "query": query, "query_type": query_type}

    except ImportError:
        log.warning("playwright_not_available", query=query)
        return {"profiles": [], "query": query, "query_type": query_type}
    except Exception as exc:
        log.error("facebook_intel_task_error", query=query, error=str(exc))
        raise self.retry(exc=exc)
