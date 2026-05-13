"""Celery task: GitHub Intel API fetch (light queue)."""
from __future__ import annotations

import asyncio
from dataclasses import asdict
from typing import Any

import structlog

from src.workers.celery_app import celery_app

log = structlog.get_logger(__name__)


@celery_app.task(
    bind=True,
    name="github_intel.fetch",
    queue="light",
    max_retries=2,
    default_retry_delay=15,
    soft_time_limit=45,
    time_limit=60,
)
def github_intel_fetch_task(self: Any, query: str, query_type: str) -> dict[str, Any]:
    """Fetch GitHub profile/search data via the public API."""
    try:
        from src.adapters.github_intel.fetcher import fetch_github
        from src.config import get_settings

        settings = get_settings()
        token = getattr(settings, "github_api_token", "") or ""

        result = asyncio.run(fetch_github(query, query_type, token=token))

        profiles_json = []
        for p in result.profiles:
            repos = [
                {
                    "name": r.name,
                    "description": r.description,
                    "stars": r.stars,
                    "forks": r.forks,
                    "language": r.language,
                    "url": r.url,
                    "is_fork": r.is_fork,
                    "topics": r.topics,
                }
                for r in p.top_repos
            ]
            profiles_json.append(
                {
                    "user_id": p.user_id,
                    "username": p.username,
                    "full_name": p.full_name,
                    "bio": p.bio,
                    "avatar_url": p.avatar_url,
                    "profile_url": p.profile_url,
                    "company": p.company,
                    "blog": p.blog,
                    "location": p.location,
                    "email": p.email,
                    "twitter_username": p.twitter_username,
                    "followers": p.followers,
                    "following": p.following,
                    "public_repos": p.public_repos,
                    "public_gists": p.public_gists,
                    "created_at": p.created_at,
                    "is_verified": p.is_verified,
                    "account_type": p.account_type,
                    "top_repos": repos,
                    "languages": p.languages,
                    "emails_in_commits": p.emails_in_commits,
                    "source": p.source,
                }
            )

        log.info("github_intel_task_done", query=query, count=len(profiles_json))
        return {"profiles": profiles_json, "query": query, "query_type": query_type}

    except Exception as exc:
        log.error("github_intel_task_error", query=query, error=str(exc))
        raise self.retry(exc=exc)
