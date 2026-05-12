"""Celery task: Instagram Intel Playwright scrape (heavy queue)."""
from __future__ import annotations

import asyncio
from typing import Any

import structlog

from src.workers.celery_app import celery_app

log = structlog.get_logger(__name__)


@celery_app.task(
    bind=True,
    name="instagram_intel.scrape",
    queue="heavy",
    max_retries=2,
    default_retry_delay=30,
    soft_time_limit=90,
    time_limit=120,
)
def instagram_intel_scrape_task(self: Any, query: str, query_type: str) -> dict[str, Any]:
    """Run a Playwright-based Instagram Intel scrape.

    Returns serialised list of profile dicts so the router can store them.
    """
    try:
        from src.adapters.instagram_intel.playwright_scraper import scrape_instagram

        result = asyncio.run(scrape_instagram(query, query_type))

        profiles_json = [
            {
                "user_id": p.user_id,
                "username": p.username,
                "full_name": p.full_name,
                "biography": p.biography,
                "profile_pic_url": p.profile_pic_url,
                "profile_url": p.profile_url,
                "follower_count": p.follower_count,
                "following_count": p.following_count,
                "media_count": p.media_count,
                "is_verified": p.is_verified,
                "is_private": p.is_private,
                "external_url": p.external_url,
                "category": p.category,
                "source": p.source,
            }
            for p in result.profiles
        ]

        log.info("instagram_intel_task_done", query=query, count=len(profiles_json))
        return {"profiles": profiles_json, "query": query, "query_type": query_type}

    except ImportError:
        log.warning("playwright_not_available", query=query)
        return {"profiles": [], "query": query, "query_type": query_type}
    except Exception as exc:
        log.error("instagram_intel_task_error", query=query, error=str(exc))
        raise self.retry(exc=exc)
