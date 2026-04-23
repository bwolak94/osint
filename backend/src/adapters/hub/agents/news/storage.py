"""News storage agent — persists final articles to the Qdrant news collection.

Runs after the CriticAgent (last step before synergy). Each non-duplicate
article is upserted with its full payload so future pipeline runs can:
  1. Deduplicate against previously seen articles (cosine > 0.92 threshold)
  2. Retrieve news articles via hybrid search from the knowledge layer

Design:
  - qdrant_upsert injected (DIP) — async callable(collection, points) → None
  - Encoder injected — async callable(text: str) → list[float]
  - When either is None, storage is skipped (graceful degradation for tests)
"""

from __future__ import annotations

from typing import Any, Callable, Coroutine

import structlog

from src.adapters.hub.agents.news.state import NewsArticle, NewsState
from src.adapters.qdrant.collections import NEWS_COLLECTION

log = structlog.get_logger(__name__)

# Type aliases for injected callables
QdrantUpsertFn = Callable[
    [str, list[dict[str, Any]]],
    Coroutine[Any, Any, None],
]
EncoderFn = Callable[[str], Coroutine[Any, Any, list[float]]]


def _build_point(article: NewsArticle, vector: list[float]) -> dict[str, Any]:
    """Build a Qdrant point dict from a finalised article."""
    return {
        "id": article.get("id", ""),
        "vector": {
            "dense": vector,
        },
        "payload": {
            "article_id": article.get("id", ""),
            "url": article.get("url", ""),
            "title": article.get("title", ""),
            "source_domain": article.get("source_domain", ""),
            "published_at": article.get("published_at", ""),
            "credibility_score": article.get("credibility_score", 0.0),
            "action_relevance_score": article.get("action_relevance_score", 0.0),
            "tags": article.get("tags") or [],
            "image_url": article.get("image_url", ""),
            "summary": article.get("summary", ""),
        },
    }


async def news_storage_agent(
    state: NewsState,
    qdrant_upsert: QdrantUpsertFn | None = None,
    encoder: EncoderFn | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Persist final articles to Qdrant news collection.

    Only stores non-duplicate articles. Skips gracefully when either
    qdrant_upsert or encoder is not configured (test / offline mode).

    Args:
        state:         Current NewsState (reads ``final_articles``).
        qdrant_upsert: Async callable(collection_name, points) → None.
        encoder:       Async callable(text) → dense vector (1536 dims).
        **kwargs:      Ignored — uniform agent signature.

    Returns:
        Partial NewsState update (adds ``stored_count`` to thoughts, no data change).
    """
    final_articles: list[NewsArticle] = list(state.get("final_articles") or [])
    thoughts: list[str] = list(state.get("thoughts") or [])

    if qdrant_upsert is None or encoder is None:
        thoughts.append(
            "NewsStorage: skipped — qdrant_upsert or encoder not configured (offline mode)."
        )
        await log.awarning("news_storage_skipped", reason="no_qdrant_or_encoder")
        return {
            "thoughts": thoughts,
            "current_step": "storage",
            "error": None,
        }

    # Only persist articles that passed deduplication
    to_store = [a for a in final_articles if not a.get("is_duplicate", False)]
    await log.ainfo("news_storage_start", total=len(final_articles), to_store=len(to_store))
    thoughts.append(f"NewsStorage: persisting {len(to_store)} article(s) to Qdrant…")

    points: list[dict[str, Any]] = []
    failed = 0

    for article in to_store:
        # Embed title + summary for semantic search / future dedup
        text_to_embed = f"{article.get('title', '')} {article.get('summary', '')}".strip()
        try:
            vector = await encoder(text_to_embed)
            points.append(_build_point(article, vector))
        except Exception as exc:
            await log.awarning("news_storage_encode_error", error=str(exc))
            failed += 1

    if points:
        try:
            await qdrant_upsert(NEWS_COLLECTION, points)
            await log.ainfo("news_storage_done", stored=len(points), failed=failed)
            thoughts.append(
                f"NewsStorage: stored {len(points)} article(s)"
                + (f", {failed} encoding error(s)." if failed else ".")
            )
        except Exception as exc:
            await log.aerror("news_storage_upsert_error", error=str(exc))
            thoughts.append(f"NewsStorage: upsert failed — {exc} (pipeline continues).")
    else:
        thoughts.append("NewsStorage: no new articles to store.")

    return {
        "thoughts": thoughts,
        "current_step": "storage",
        "error": None,
    }
