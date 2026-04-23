"""News validator agent — scores credibility and deduplicates articles.

Credibility heuristic (rule-based, Phase 2):
  +0.2  URL uses HTTPS
  +0.3  domain not in known spam/low-quality blocklist
  +0.3  article has non-trivial content (> 100 chars)
  +0.2  published_at is present (non-empty)

Dedup: if a Qdrant searcher is provided, articles with cosine similarity > 0.92
to an existing document are marked is_duplicate=True and filtered out.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import structlog

from src.adapters.hub.agents.news.state import NewsArticle, NewsState

log = structlog.get_logger(__name__)

_CREDIBILITY_THRESHOLD = 0.6
_DEDUP_SIMILARITY_THRESHOLD = 0.92

# Known low-quality / spam domains (extend in production via config)
_BLOCKLIST: frozenset[str] = frozenset(
    {
        "spam-news.com",
        "clickbait.net",
        "fakenews.info",
        "tabloid-daily.co",
    }
)


def _score_credibility(url: str, domain: str, content: str, published_at: str) -> float:
    """Compute a 0.0–1.0 credibility score for an article."""
    score = 0.0

    # HTTPS check
    try:
        parsed = urlparse(url)
        if parsed.scheme == "https":
            score += 0.2
    except Exception:
        pass

    # Domain not in blocklist
    if domain not in _BLOCKLIST:
        score += 0.3

    # Non-trivial content
    if len(content) > 100:
        score += 0.3

    # Has a published date
    if published_at and published_at.strip():
        score += 0.2

    return round(min(score, 1.0), 4)


async def _check_duplicate(
    article: NewsArticle,
    qdrant_searcher: Any,
) -> bool:
    """Return True if the article is semantically similar to an existing document."""
    try:
        results = await qdrant_searcher.retrieve(
            query=article.get("content", ""),
            top_k=1,
        )
        if results and results[0].get("score", 0.0) > _DEDUP_SIMILARITY_THRESHOLD:
            return True
    except Exception as exc:
        await log.awarning("dedup_check_error", error=str(exc))
    return False


async def news_validator_agent(
    state: NewsState,
    qdrant_searcher: Any | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Score credibility, detect duplicates, and filter low-quality articles.

    Args:
        state:          Current NewsState (reads ``articles``).
        qdrant_searcher: Injected searcher for semantic dedup (None → skip dedup).
        **kwargs:       Ignored — uniform agent signature.

    Returns:
        Partial NewsState update with ``validated_articles``.
    """
    articles: list[NewsArticle] = list(state.get("articles") or [])
    thoughts: list[str] = list(state.get("thoughts") or [])

    await log.ainfo("news_validator_start", article_count=len(articles))
    thoughts.append(f"NewsValidator: validating {len(articles)} article(s)…")

    scored: list[NewsArticle] = []
    for article in articles:
        url = article.get("url", "")
        domain = article.get("source_domain", "")
        content = article.get("content", "")
        published_at = article.get("published_at", "")

        credibility = _score_credibility(url, domain, content, published_at)
        article = dict(article)  # type: ignore[assignment]
        article["credibility_score"] = credibility  # type: ignore[index]

        # Dedup check
        if qdrant_searcher is not None:
            article["is_duplicate"] = await _check_duplicate(article, qdrant_searcher)  # type: ignore[index]
        else:
            article["is_duplicate"] = False  # type: ignore[index]

        scored.append(article)  # type: ignore[arg-type]

    # Filter: keep only articles that pass credibility and are not duplicates
    validated = [
        a for a in scored
        if a.get("credibility_score", 0.0) >= _CREDIBILITY_THRESHOLD
        and not a.get("is_duplicate", False)
    ]

    removed = len(scored) - len(validated)
    thoughts.append(
        f"NewsValidator: {len(validated)} article(s) passed (removed {removed} low-quality/duplicate)."
    )

    await log.ainfo("news_validator_done", validated=len(validated), removed=removed)

    return {
        "articles": scored,
        "validated_articles": validated,
        "thoughts": thoughts,
        "current_step": "validator",
        "error": None,
    }
