"""Celery task: LinkedIn Intel Playwright scrape (heavy queue)."""
from __future__ import annotations

import asyncio
from typing import Any

import structlog

from src.workers.celery_app import celery_app

log = structlog.get_logger(__name__)


@celery_app.task(
    bind=True,
    name="linkedin_intel.scrape",
    queue="heavy",
    max_retries=2,
    default_retry_delay=30,
    soft_time_limit=120,
    time_limit=150,
)
def linkedin_intel_scrape_task(self: Any, query: str, query_type: str) -> dict[str, Any]:
    """Run a Playwright-based LinkedIn Intel scrape via Yahoo dork."""
    try:
        from src.adapters.linkedin_intel.playwright_scraper import scrape_linkedin

        result = asyncio.run(scrape_linkedin(query, query_type))

        profiles_json = [
            {
                "username": p.username,
                "full_name": p.full_name,
                "headline": p.headline,
                "location": p.location,
                "profile_pic_url": p.profile_pic_url,
                "profile_url": p.profile_url,
                "connections": p.connections,
                "company": p.company,
                "school": p.school,
                "source": p.source,
            }
            for p in result.profiles
        ]

        log.info("linkedin_intel_task_done", query=query, count=len(profiles_json))
        return {"profiles": profiles_json, "query": query, "query_type": query_type}

    except ImportError:
        log.warning("playwright_not_available", query=query)
        return {"profiles": [], "query": query, "query_type": query_type}
    except Exception as exc:
        log.error("linkedin_intel_task_error", query=query, error=str(exc))
        raise self.retry(exc=exc)
