"""News summary agent — generates article summaries via LLM or extractive fallback.

Design: LLMSummarizer is injected (DIP). When None, an extractive heuristic
produces a summary from the first 3 sentences (or 300 chars, whichever shorter).
"""

from __future__ import annotations

import re
from typing import Any, Protocol

import structlog

from src.adapters.hub.agents.news.state import NewsArticle, NewsState

log = structlog.get_logger(__name__)

_EXTRACTIVE_MAX_CHARS = 300
_EXTRACTIVE_MAX_SENTENCES = 3


class LLMSummarizer(Protocol):
    """Interface for LLM-based text summarisation."""

    async def summarize(self, content: str, context: str = "") -> str: ...


def _extractive_summary(content: str) -> str:
    """Extract first N sentences up to _EXTRACTIVE_MAX_CHARS characters."""
    # Split on sentence boundaries
    sentences = re.split(r"(?<=[.!?])\s+", content.strip())
    selected: list[str] = []
    total_chars = 0

    for sentence in sentences[:_EXTRACTIVE_MAX_SENTENCES]:
        if total_chars + len(sentence) > _EXTRACTIVE_MAX_CHARS:
            break
        selected.append(sentence)
        total_chars += len(sentence)

    summary = " ".join(selected) if selected else content[:_EXTRACTIVE_MAX_CHARS]
    return summary.strip()


async def news_summary_agent(
    state: NewsState,
    llm_summarizer: LLMSummarizer | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Summarise each enriched article.

    Args:
        state:          Current NewsState (reads ``enriched_articles``).
        llm_summarizer: Injected LLMSummarizer (None → extractive fallback).
        **kwargs:       Ignored — uniform agent signature.

    Returns:
        Partial NewsState update with ``summaries``.
    """
    enriched: list[NewsArticle] = list(state.get("enriched_articles") or [])
    thoughts: list[str] = list(state.get("thoughts") or [])

    mode = "LLM" if llm_summarizer else "extractive"
    await log.ainfo("news_summary_start", article_count=len(enriched), mode=mode)
    thoughts.append(f"NewsSummary: summarising {len(enriched)} article(s) via {mode} method…")

    summaries: list[NewsArticle] = []
    for article in enriched:
        content = article.get("content", "")
        article_copy = dict(article)  # type: ignore[assignment]

        if llm_summarizer is not None:
            try:
                summary_text = await llm_summarizer.summarize(content)
            except Exception as exc:
                await log.awarning("llm_summarizer_error", error=str(exc))
                summary_text = _extractive_summary(content)
        else:
            summary_text = _extractive_summary(content)

        article_copy["summary"] = summary_text  # type: ignore[index]
        article_copy["critique_score"] = 0.0  # filled by CriticAgent  # type: ignore[index]
        summaries.append(article_copy)  # type: ignore[arg-type]

    thoughts.append(f"NewsSummary: {len(summaries)} summaries generated.")
    await log.ainfo("news_summary_done", summaries=len(summaries))

    return {
        "summaries": summaries,
        "thoughts": thoughts,
        "current_step": "summary",
        "error": None,
    }
