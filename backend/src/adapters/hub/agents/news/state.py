"""NewsState — TypedDicts for the news research pipeline.

Separate from HubState so the NewsAgentGraph can be tested in isolation
and composed cleanly with the main graph.
"""

from __future__ import annotations

from typing import TypedDict


class NewsArticle(TypedDict, total=False):
    """A single article flowing through the news pipeline."""

    id: str                     # uuid string
    url: str
    title: str
    content: str
    published_at: str           # ISO 8601 datetime string
    source_domain: str
    image_url: str              # optional thumbnail (Tavily include_images=True)
    credibility_score: float    # 0.0–1.0
    is_duplicate: bool
    tags: list[str]
    relevance_score: float
    summary: str
    critique_score: float       # reflection loop score (0.0–1.0)
    critique_feedback: str      # last critic feedback (used in retry prompt)
    action_relevance_score: float


class NewsState(TypedDict, total=False):
    """Shared state flowing through the news multi-agent pipeline."""

    # ── Identity ─────────────────────────────────────────────────────────────
    task_id: str
    user_id: str

    # ── Input ────────────────────────────────────────────────────────────────
    search_query: str
    user_preferences: dict[str, object]

    # ── Pipeline stages ───────────────────────────────────────────────────────
    raw_results: list[dict[str, object]]
    articles: list[NewsArticle]
    validated_articles: list[NewsArticle]
    enriched_articles: list[NewsArticle]
    summaries: list[NewsArticle]
    final_articles: list[NewsArticle]

    # ── Outputs ──────────────────────────────────────────────────────────────
    action_signals: list[dict[str, object]]

    # ── Observability ────────────────────────────────────────────────────────
    thoughts: list[str]
    current_step: str
    error: str | None
    completed: bool
