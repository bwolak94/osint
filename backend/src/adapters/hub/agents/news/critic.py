"""News critic agent — reflection loop that scores summaries and requests retries.

Design: LLMCritic is injected (DIP). When None, returns mock score 0.85
(always passes). When provided, low-scoring summaries (< 0.8) are re-summarised
once before final acceptance.

The reflection loop runs at most `max_retries` times per article.
"""

from __future__ import annotations

from typing import Any, Protocol

import structlog

from src.adapters.hub.agents.news.state import NewsArticle, NewsState
from src.adapters.hub.agents.news.summary import LLMSummarizer, _extractive_summary

log = structlog.get_logger(__name__)

_CRITIQUE_PASS_THRESHOLD = 0.8
_MOCK_CRITIQUE_SCORE = 0.85


class LLMCritic(Protocol):
    """Interface for LLM-based summary critique (returns score + feedback)."""

    async def critique(self, content: str, summary: str) -> tuple[float, str]: ...


async def _get_score(
    llm_critic: LLMCritic | None,
    content: str,
    summary: str,
) -> tuple[float, str]:
    """Return (score, feedback) from real critic or mock."""
    if llm_critic is None:
        return _MOCK_CRITIQUE_SCORE, "mock: summary is acceptable"
    return await llm_critic.critique(content, summary)


async def news_critic_agent(
    state: NewsState,
    llm_critic: LLMCritic | None = None,
    llm_summarizer: LLMSummarizer | None = None,
    max_retries: int = 2,
    **kwargs: Any,
) -> dict[str, Any]:
    """Score each summary; retry once if below quality threshold.

    Args:
        state:          Current NewsState (reads ``summaries``).
        llm_critic:     Injected LLMCritic (None → mock score 0.85).
        llm_summarizer: Injected LLMSummarizer for retry re-summarisation.
        max_retries:    Maximum reflection loop iterations per article.
        **kwargs:       Ignored — uniform agent signature.

    Returns:
        Partial NewsState update with ``final_articles``.
    """
    summaries: list[NewsArticle] = list(state.get("summaries") or [])
    thoughts: list[str] = list(state.get("thoughts") or [])

    await log.ainfo("news_critic_start", article_count=len(summaries))
    mode = "LLM" if llm_critic else "mock"
    thoughts.append(f"NewsCritic: critiquing {len(summaries)} summary/summaries ({mode} mode)…")

    final: list[NewsArticle] = []

    for article in summaries:
        content = article.get("content", "")
        summary = article.get("summary", "")
        article_copy = dict(article)  # type: ignore[assignment]

        score, feedback = await _get_score(llm_critic, content, summary)

        # Reflection loop: retry if score is below threshold
        retry_count = 0
        while score < _CRITIQUE_PASS_THRESHOLD and retry_count < max_retries:
            retry_count += 1
            await log.awarning(
                "news_critic_retry",
                score=score,
                feedback=feedback,
                retry=retry_count,
            )
            thoughts.append(
                f"NewsCritic: summary score {score:.2f} < {_CRITIQUE_PASS_THRESHOLD} — retrying ({retry_count}/{max_retries})."
            )

            # Re-summarise — pass critic feedback as context so the LLM
            # can address the specific quality issues identified
            improvement_context = (
                f"Previous score: {score:.2f}/1.0. Critic feedback: {feedback}. "
                "Only critique factual accuracy and completeness — not style."
            )
            if llm_summarizer is not None:
                try:
                    summary = await llm_summarizer.summarize(content, context=improvement_context)
                except Exception:
                    summary = _extractive_summary(content)
            else:
                summary = _extractive_summary(content)

            score, feedback = await _get_score(llm_critic, content, summary)

        article_copy["summary"] = summary  # type: ignore[index]
        article_copy["critique_score"] = round(score, 4)  # type: ignore[index]
        article_copy["critique_feedback"] = feedback  # type: ignore[index]
        final.append(article_copy)  # type: ignore[arg-type]

    thoughts.append(f"NewsCritic: {len(final)} article(s) finalised.")
    avg_score = (
        round(sum(a.get("critique_score", 0.0) for a in final) / len(final), 4)
        if final else 0.0
    )
    await log.ainfo("news_critic_done", final_articles=len(final), avg_critique_score=avg_score)

    return {
        "final_articles": final,
        "thoughts": thoughts,
        "current_step": "critic",
        "error": None,
    }
