"""News synergy agent — identifies high-relevance articles and emits action signals.

For each article whose action_relevance_score exceeds the threshold, this agent:
  1. Builds an action signal dict with a suggested follow-up task.
  2. Optionally emits the signal via an event_publisher (Redis pub/sub or similar).

Design: event_publisher is injected (DIP) — callable(event_name, payload).
"""

from __future__ import annotations

import uuid
from typing import Any, Callable, Coroutine

import structlog

from src.adapters.hub.agents.news.state import NewsArticle, NewsState

log = structlog.get_logger(__name__)

_ACTION_RELEVANCE_THRESHOLD = 0.75

# Type alias for an async event publisher
EventPublisher = Callable[[str, dict[str, Any]], Coroutine[Any, Any, None]]


def _suggest_task(article: NewsArticle) -> str:
    """Generate a suggested follow-up task title based on article tags."""
    tags = article.get("tags") or []
    title = article.get("title", "article")

    if "security" in tags:
        return f"Investigate security implications: {title}"
    if "regulation" in tags:
        return f"Review regulatory impact: {title}"
    if "technology" in tags:
        return f"Evaluate technology relevance: {title}"
    if "finance" in tags:
        return f"Assess financial impact: {title}"
    return f"Follow up on: {title}"


async def news_synergy_agent(
    state: NewsState,
    event_publisher: EventPublisher | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Identify action-worthy articles and emit signals.

    Args:
        state:           Current NewsState (reads ``final_articles``).
        event_publisher: Async callable(event_name, payload) for signal emission.
        **kwargs:        Ignored — uniform agent signature.

    Returns:
        Partial NewsState update with ``action_signals`` and ``completed=True``.
    """
    final_articles: list[NewsArticle] = list(state.get("final_articles") or [])
    thoughts: list[str] = list(state.get("thoughts") or [])

    await log.ainfo("news_synergy_start", article_count=len(final_articles))
    thoughts.append(f"NewsSynergy: scanning {len(final_articles)} article(s) for action signals…")

    action_signals: list[dict[str, Any]] = []

    for article in final_articles:
        score = article.get("action_relevance_score", 0.0)
        if score <= _ACTION_RELEVANCE_THRESHOLD:
            continue

        signal: dict[str, Any] = {
            "finding_id": str(uuid.uuid4()),
            "title": article.get("title", ""),
            "suggested_task": _suggest_task(article),
            "action_relevance_score": score,
            "url": article.get("url", ""),
            "tags": article.get("tags") or [],
        }
        action_signals.append(signal)

        if event_publisher is not None:
            try:
                await event_publisher("news_action_signal", signal)
            except Exception as exc:
                await log.awarning("synergy_publish_error", error=str(exc))

    thoughts.append(f"NewsSynergy: emitted {len(action_signals)} action signal(s).")
    await log.ainfo("news_synergy_done", action_signals=len(action_signals))

    return {
        "action_signals": action_signals,
        "thoughts": thoughts,
        "current_step": "synergy",
        "completed": True,
        "error": None,
    }
