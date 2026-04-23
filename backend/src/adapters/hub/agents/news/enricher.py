"""News enricher agent — tags articles and computes relevance scores.

Tag extraction: keyword matching across common NLP categories (person, org,
location, regulation, technology).

Relevance scoring: if user has news_topics preferences, we check topic overlap
with article content; otherwise defaults to 0.5.

action_relevance_score = relevance_score × credibility_score
"""

from __future__ import annotations

from typing import Any

import structlog

from src.adapters.hub.agents.news.state import NewsArticle, NewsState

log = structlog.get_logger(__name__)

# Simple keyword-based taxonomy for Phase 2
_TAG_TAXONOMY: dict[str, list[str]] = {
    "person": ["ceo", "founder", "researcher", "scientist", "politician", "president", "executive"],
    "organization": ["company", "startup", "university", "government", "agency", "institute", "corp"],
    "location": ["city", "country", "region", "europe", "asia", "usa", "uk", "global", "worldwide"],
    "regulation": ["law", "regulation", "gdpr", "compliance", "policy", "ban", "ruling", "legislation"],
    "technology": ["ai", "machine learning", "model", "llm", "gpu", "cloud", "software", "algorithm"],
    "finance": ["funding", "investment", "ipo", "revenue", "profit", "market", "stock", "capital"],
    "security": ["vulnerability", "exploit", "breach", "hack", "ransomware", "malware", "cve"],
}


def _extract_tags(content: str, title: str = "") -> list[str]:
    """Return a list of category tags for an article based on keyword matching."""
    text = (title + " " + content).lower()
    tags: list[str] = []
    for tag, keywords in _TAG_TAXONOMY.items():
        if any(kw in text for kw in keywords):
            tags.append(tag)
    return tags


def _compute_relevance(
    content: str,
    title: str,
    news_topics: list[str],
) -> float:
    """Score 0.0–1.0 based on overlap between user interests and article text."""
    if not news_topics:
        return 0.5  # neutral when no preference configured

    text = (title + " " + content).lower()
    matched = sum(1 for topic in news_topics if topic.lower() in text)
    return round(min(matched / len(news_topics), 1.0), 4)


async def news_enricher_agent(
    state: NewsState,
    qdrant_searcher: Any | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Tag and score each validated article.

    Args:
        state:          Current NewsState (reads ``validated_articles``).
        qdrant_searcher: Unused in Phase 2 (reserved for semantic expansion).
        **kwargs:       Ignored — uniform agent signature.

    Returns:
        Partial NewsState update with ``enriched_articles``.
    """
    validated: list[NewsArticle] = list(state.get("validated_articles") or [])
    thoughts: list[str] = list(state.get("thoughts") or [])
    prefs: dict[str, Any] = state.get("user_preferences") or {}  # type: ignore[assignment]
    news_topics: list[str] = prefs.get("news_topics") or []  # type: ignore[index]

    await log.ainfo("news_enricher_start", article_count=len(validated))
    thoughts.append(f"NewsEnricher: enriching {len(validated)} article(s)…")

    enriched: list[NewsArticle] = []
    for article in validated:
        content = article.get("content", "")
        title = article.get("title", "")
        credibility = article.get("credibility_score", 0.5)

        tags = _extract_tags(content, title)
        relevance = _compute_relevance(content, title, news_topics)
        action_relevance = round(relevance * credibility, 4)

        enriched_article = dict(article)  # type: ignore[assignment]
        enriched_article["tags"] = tags  # type: ignore[index]
        enriched_article["relevance_score"] = relevance  # type: ignore[index]
        enriched_article["action_relevance_score"] = action_relevance  # type: ignore[index]
        enriched.append(enriched_article)  # type: ignore[arg-type]

    thoughts.append(f"NewsEnricher: tagged and scored {len(enriched)} article(s).")
    await log.ainfo("news_enricher_done", enriched=len(enriched))

    return {
        "enriched_articles": enriched,
        "thoughts": thoughts,
        "current_step": "enricher",
        "error": None,
    }
