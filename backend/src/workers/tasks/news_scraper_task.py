"""Celery task: periodic RSS news scraping → Qdrant storage.

Runs every 30 minutes via Celery beat. Fetches ~15 RSS feeds,
validates + enriches articles, and upserts them to the Qdrant news
collection so the News RAG chat always has fresh data.

No LLM calls during scraping — summaries use extractive fallback to
keep the batch fast and cheap. The critic reflection loop is skipped.
"""
from __future__ import annotations

import asyncio
import re as re_mod
import textwrap
from datetime import datetime, timezone
from typing import Any

import structlog

from src.workers.celery_app import celery_app

log = structlog.get_logger(__name__)

# Safety limit for the dedup scroll loop
_MAX_SCROLL_PAGES = 100


async def _run_scrape() -> dict[str, Any]:
    from src.adapters.news.rss_scraper import scrape_all_feeds
    from src.adapters.hub.agents.news.validator import news_validator_agent
    from src.adapters.hub.agents.news.enricher import news_enricher_agent
    from src.adapters.hub.agents.news.storage import news_storage_agent
    from src.adapters.qdrant.client import get_qdrant_client
    from src.adapters.qdrant.collections import (
        NEWS_COLLECTION,
        DENSE_VECTOR_NAME,
        QdrantCollectionManager,
    )
    from src.config import get_settings

    settings = get_settings()

    # ── Get async Redis client for feed registry ───────────────────────────────
    redis_async = None
    try:
        import redis.asyncio as aioredis
        redis_async = aioredis.from_url(settings.redis_url, decode_responses=True)
    except Exception as exc:
        log.warning("news_scraper_redis_unavailable", error=str(exc))

    raw_articles = await scrape_all_feeds(redis=redis_async)
    log.info("news_scraper_fetched", count=len(raw_articles))

    if redis_async is not None:
        try:
            await redis_async.aclose()
        except Exception:
            pass

    if not raw_articles:
        return {"scraped": 0, "stored": 0}

    # ── Qdrant client ──────────────────────────────────────────────────────────
    qdrant = get_qdrant_client()

    # ── Ensure news collection exists ──────────────────────────────────────────
    mgr = QdrantCollectionManager(qdrant)
    await mgr.ensure_news_collection()

    # ── Dense encoder: FastEmbed (local, no API key needed) ───────────────────
    # Uses BAAI/bge-small-en-v1.5 (384-dim) — matches NEWS_DENSE_DIM in collections.py
    encoder = None
    try:
        from fastembed import TextEmbedding as _TextEmbedding
        import asyncio as _asyncio

        _fe_model = _TextEmbedding(model_name="BAAI/bge-small-en-v1.5")

        async def _encode(text: str) -> list[float]:
            loop = _asyncio.get_event_loop()
            vectors = await loop.run_in_executor(
                None,
                lambda: list(_fe_model.embed([text[:2000]]))[0],
            )
            return [float(v) for v in vectors]

        encoder = _encode
        log.info("news_scraper_fastembed_ready")
    except Exception as exc:
        log.warning("news_scraper_encoder_unavailable", error=str(exc))

    # ── Qdrant upsert helper ───────────────────────────────────────────────────
    async def _qdrant_upsert(collection: str, points: list[dict[str, Any]]) -> None:
        from qdrant_client.models import PointStruct

        structs = []
        for p in points:
            vector_data = p.get("vector", {})
            if isinstance(vector_data, dict):
                structs.append(
                    PointStruct(
                        id=p["id"],
                        vector=vector_data,
                        payload=p.get("payload", {}),
                    )
                )
            else:
                structs.append(
                    PointStruct(
                        id=p["id"],
                        vector={DENSE_VECTOR_NAME: vector_data},
                        payload=p.get("payload", {}),
                    )
                )
        await qdrant.upsert(collection_name=collection, points=structs, wait=True)

    # ── URL-based dedup: scroll Qdrant for already-known article URLs ──────────
    known_urls: set[str] = set()
    try:
        offset = None
        page_count = 0
        while page_count < _MAX_SCROLL_PAGES:
            page_count += 1
            scroll_result = await qdrant.scroll(
                collection_name=NEWS_COLLECTION,
                scroll_filter=None,
                limit=1000,
                offset=offset,
                with_payload=["url"],
                with_vectors=False,
            )
            points_batch, next_offset = scroll_result
            for pt in points_batch:
                if pt.payload and pt.payload.get("url"):
                    known_urls.add(pt.payload["url"])
            if next_offset is None:
                break
            offset = next_offset
    except Exception as exc:
        log.warning("news_scraper_dedup_scroll_error", error=str(exc))

    # Filter out articles we already have
    new_articles = [a for a in raw_articles if a.get("url") not in known_urls]
    log.info(
        "news_scraper_dedup",
        total=len(raw_articles),
        new=len(new_articles),
        known=len(known_urls),
    )

    if not new_articles:
        return {"scraped": len(raw_articles), "new": 0, "stored": 0}

    # ── Build a minimal NewsState for the pipeline agents ─────────────────────
    state: dict[str, Any] = {
        "task_id": f"scraper-{datetime.now(timezone.utc).isoformat()}",
        "user_id": "system",
        "search_query": "rss scrape",
        "user_preferences": {},
        "raw_results": new_articles,
        "articles": new_articles,
        "validated_articles": [],
        "enriched_articles": [],
        "summaries": [],
        "final_articles": [],
        "action_signals": [],
        "thoughts": [],
        "current_step": "validator",
        "error": None,
        "completed": False,
    }

    # ── Validator ─────────────────────────────────────────────────────────────
    # Stub searcher — URL dedup already done above; semantic dedup not needed.
    class _StubRetriever:
        async def retrieve(self, query: str, top_k: int = 5) -> list:
            return []

    # Fix 7: use correct parameter name 'qdrant_searcher' (matches validator signature)
    val_result = await news_validator_agent(
        state=state,  # type: ignore[arg-type]
        qdrant_searcher=_StubRetriever(),
    )
    state.update(val_result)

    validated = state.get("validated_articles", [])
    if not validated:
        return {"scraped": len(raw_articles), "new": len(new_articles), "stored": 0}

    state["articles"] = validated

    # ── Enricher ───────────────────────────────────────────────────────────────
    enrich_result = await news_enricher_agent(state=state)  # type: ignore[arg-type]
    state.update(enrich_result)

    enriched = state.get("enriched_articles", [])
    if not enriched:
        return {"scraped": len(raw_articles), "new": len(new_articles), "stored": 0}

    # ── Extractive summary (fast, no LLM) and action_relevance_score ──────────
    for art in enriched:
        content = art.get("content", "")
        sentences = re_mod.split(r"(?<=[.!?])\s+", content)
        summary = " ".join(sentences[:3]) if sentences else content
        art["summary"] = textwrap.shorten(summary, width=400, placeholder="…")
        art["critique_score"] = 0.7  # default score for RSS-scraped articles
        # Compute action_relevance_score so synergy signals can fire
        credibility = art.get("credibility_score", 0.7)
        relevance = art.get("relevance_score", 0.5)
        art["action_relevance_score"] = round(credibility * relevance, 3)

    state["final_articles"] = enriched

    # ── Storage ────────────────────────────────────────────────────────────────
    await news_storage_agent(
        state=state,  # type: ignore[arg-type]
        qdrant_upsert=_qdrant_upsert if encoder else None,
        encoder=encoder,
    )

    stored_count = len([a for a in enriched if not a.get("is_duplicate", False)])
    log.info(
        "news_scraper_complete",
        scraped=len(raw_articles),
        new=len(new_articles),
        stored=stored_count,
    )
    return {"scraped": len(raw_articles), "new": len(new_articles), "stored": stored_count}


@celery_app.task(
    name="news.scrape_all",
    queue="light",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    ignore_result=True,  # Fix 12: results are never consumed by callers
)
def scrape_news_task(self: Any) -> dict[str, Any]:
    """Periodic task: scrape all configured RSS feeds and store in Qdrant."""
    try:
        return asyncio.run(_run_scrape())
    except Exception as exc:
        log.error("news_scraper_task_error", error=str(exc))
        raise self.retry(exc=exc)
