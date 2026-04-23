"""Tests for the News pipeline agents (searcher, validator, enricher, summary, critic, synergy)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.adapters.hub.agents.news.critic import news_critic_agent
from src.adapters.hub.agents.news.enricher import _extract_tags, news_enricher_agent
from src.adapters.hub.agents.news.searcher import _extract_domain, news_searcher_agent
from src.adapters.hub.agents.news.state import NewsArticle, NewsState
from src.adapters.hub.agents.news.summary import _extractive_summary, news_summary_agent
from src.adapters.hub.agents.news.synergy import news_synergy_agent
from src.adapters.hub.agents.news.validator import _score_credibility, news_validator_agent


def _make_state(**kwargs: object) -> NewsState:
    base: NewsState = {
        "task_id": "t-1",
        "user_id": "u-1",
        "search_query": "AI trends",
        "user_preferences": {},
        "raw_results": [],
        "articles": [],
        "validated_articles": [],
        "enriched_articles": [],
        "summaries": [],
        "final_articles": [],
        "action_signals": [],
        "thoughts": [],
        "current_step": "start",
        "error": None,
        "completed": False,
    }
    base.update(kwargs)  # type: ignore[typeddict-item]
    return base


def _make_article(**kwargs: object) -> NewsArticle:
    base = NewsArticle(
        id="art-1",
        url="https://example.com/ai-news",
        title="AI News Article",
        content="This is a substantial article about artificial intelligence developments.",
        published_at="2026-04-22T10:00:00Z",
        source_domain="example.com",
        credibility_score=0.8,
        is_duplicate=False,
        tags=[],
        relevance_score=0.5,
        summary="",
        critique_score=0.0,
        action_relevance_score=0.4,
    )
    base.update(kwargs)  # type: ignore[typeddict-item]
    return base


# ── SearcherAgent ────────────────────────────────────────────────────────────

class TestNewsSearcherAgent:
    async def test_returns_mock_articles_when_no_searcher(self) -> None:
        state = _make_state()
        result = await news_searcher_agent(state)
        assert len(result["articles"]) == 3  # 3 mock articles
        assert result["error"] is None
        assert result["current_step"] == "searcher"

    async def test_each_mock_article_has_required_fields(self) -> None:
        state = _make_state()
        result = await news_searcher_agent(state)
        for article in result["articles"]:
            assert "url" in article
            assert "title" in article
            assert "content" in article
            assert "id" in article
            assert "source_domain" in article

    async def test_tavily_searcher_called_with_correct_params(self) -> None:
        mock_searcher = AsyncMock()
        mock_searcher.search.return_value = [
            {
                "url": "https://news.example.com/story",
                "title": "Test Story",
                "content": "Long content here.",
                "published_date": "2026-04-22T09:00:00Z",
            }
        ]
        state = _make_state(search_query="test query")
        result = await news_searcher_agent(state, tavily_searcher=mock_searcher)
        mock_searcher.search.assert_awaited_once_with(
            query="test query",
            search_depth="advanced",
            max_results=10,
            include_images=True,
        )
        assert len(result["articles"]) == 1

    async def test_handles_empty_tavily_results(self) -> None:
        mock_searcher = AsyncMock()
        mock_searcher.search.return_value = []
        state = _make_state()
        result = await news_searcher_agent(state, tavily_searcher=mock_searcher)
        assert result["articles"] == []
        assert result["error"] is None

    async def test_extract_domain_from_url(self) -> None:
        assert _extract_domain("https://example.com/path") == "example.com"
        assert _extract_domain("http://sub.domain.org") == "sub.domain.org"

    async def test_tavily_error_returns_error_state(self) -> None:
        mock_searcher = AsyncMock()
        mock_searcher.search.side_effect = RuntimeError("network error")
        state = _make_state()
        result = await news_searcher_agent(state, tavily_searcher=mock_searcher)
        assert result["error"] is not None
        assert "network error" in result["error"]


# ── ValidatorAgent ───────────────────────────────────────────────────────────

class TestNewsValidatorAgent:
    def test_credibility_https_scores_higher(self) -> None:
        score_https = _score_credibility(
            "https://example.com", "example.com", "A" * 200, "2026-04-22T10:00:00Z"
        )
        score_http = _score_credibility(
            "http://example.com", "example.com", "A" * 200, "2026-04-22T10:00:00Z"
        )
        assert score_https > score_http

    def test_credibility_blocklisted_domain_penalised(self) -> None:
        good = _score_credibility("https://good.com", "good.com", "A" * 200, "2026-04-22")
        bad = _score_credibility("https://spam-news.com", "spam-news.com", "A" * 200, "2026-04-22")
        assert good > bad

    def test_credibility_short_content_penalised(self) -> None:
        long_score = _score_credibility("https://a.com", "a.com", "A" * 200, "2026-04-22")
        short_score = _score_credibility("https://a.com", "a.com", "short", "2026-04-22")
        assert long_score > short_score

    def test_credibility_missing_date_penalised(self) -> None:
        with_date = _score_credibility("https://a.com", "a.com", "A" * 200, "2026-04-22")
        without_date = _score_credibility("https://a.com", "a.com", "A" * 200, "")
        assert with_date > without_date

    async def test_filters_low_credibility_articles(self) -> None:
        articles = [
            _make_article(
                url="http://spam-news.com",
                source_domain="spam-news.com",
                content="short",
                published_at="",
            ),
            _make_article(
                url="https://reliable.com/article",
                source_domain="reliable.com",
                content="A" * 300,
                published_at="2026-04-22T10:00:00Z",
            ),
        ]
        state = _make_state(articles=articles)
        result = await news_validator_agent(state)
        # Only the high-credibility article should survive
        validated = result["validated_articles"]
        assert len(validated) == 1
        assert validated[0]["source_domain"] == "reliable.com"

    async def test_dedup_marks_similar_articles(self) -> None:
        mock_qdrant = AsyncMock()
        mock_qdrant.retrieve.return_value = [{"score": 0.95}]
        articles = [_make_article(content="A" * 200)]
        state = _make_state(articles=articles)
        result = await news_validator_agent(state, qdrant_searcher=mock_qdrant)
        # Article should be marked as duplicate and filtered out
        assert result["articles"][0]["is_duplicate"] is True
        assert len(result["validated_articles"]) == 0

    async def test_no_qdrant_skips_dedup(self) -> None:
        articles = [_make_article()]
        state = _make_state(articles=articles)
        result = await news_validator_agent(state, qdrant_searcher=None)
        assert result["articles"][0]["is_duplicate"] is False


# ── EnricherAgent ────────────────────────────────────────────────────────────

class TestNewsEnricherAgent:
    def test_extract_tags_technology(self) -> None:
        tags = _extract_tags("New AI model released for cloud computing")
        assert "technology" in tags

    def test_extract_tags_regulation(self) -> None:
        tags = _extract_tags("New GDPR regulation compliance required")
        assert "regulation" in tags

    def test_extract_tags_security(self) -> None:
        tags = _extract_tags("Critical vulnerability CVE-2026-1234 discovered")
        assert "security" in tags

    def test_extract_tags_multiple_categories(self) -> None:
        tags = _extract_tags("AI startup funding raises regulation concerns")
        assert len(tags) >= 2

    async def test_relevance_score_matches_user_topics(self) -> None:
        articles = [_make_article(content="This article is about artificial intelligence AI")]
        state = _make_state(
            validated_articles=articles,
            user_preferences={"news_topics": ["AI", "machine learning"]},
        )
        result = await news_enricher_agent(state)
        enriched = result["enriched_articles"]
        assert enriched[0]["relevance_score"] > 0.0

    async def test_action_relevance_is_product_of_relevance_and_credibility(self) -> None:
        articles = [_make_article(credibility_score=0.8, content="AI developments")]
        state = _make_state(
            validated_articles=articles,
            user_preferences={"news_topics": ["AI"]},
        )
        result = await news_enricher_agent(state)
        enriched = result["enriched_articles"][0]
        expected = round(enriched["relevance_score"] * enriched["credibility_score"], 4)
        assert enriched["action_relevance_score"] == pytest.approx(expected, abs=0.001)

    async def test_no_preferences_yields_neutral_relevance(self) -> None:
        articles = [_make_article(content="random content")]
        state = _make_state(validated_articles=articles, user_preferences={})
        result = await news_enricher_agent(state)
        assert result["enriched_articles"][0]["relevance_score"] == 0.5


# ── SummaryAgent ─────────────────────────────────────────────────────────────

class TestNewsSummaryAgent:
    def test_extractive_summary_respects_max_chars(self) -> None:
        content = "First sentence. Second sentence. Third sentence. Fourth sentence that is very long."
        summary = _extractive_summary(content)
        assert len(summary) <= 300

    def test_extractive_summary_max_three_sentences(self) -> None:
        content = "One. Two. Three. Four. Five."
        summary = _extractive_summary(content)
        # Should not include "Four" or "Five"
        assert summary.count(".") <= 3

    async def test_fallback_when_no_llm(self) -> None:
        articles = [_make_article(content="First sentence. Second sentence. Third sentence.")]
        state = _make_state(enriched_articles=articles)
        result = await news_summary_agent(state, llm_summarizer=None)
        summaries = result["summaries"]
        assert len(summaries) == 1
        assert summaries[0]["summary"] != ""

    async def test_llm_summarizer_called(self) -> None:
        mock_llm = AsyncMock()
        mock_llm.summarize.return_value = "LLM-generated summary."
        articles = [_make_article(content="Long content...")]
        state = _make_state(enriched_articles=articles)
        result = await news_summary_agent(state, llm_summarizer=mock_llm)
        mock_llm.summarize.assert_awaited_once()
        assert result["summaries"][0]["summary"] == "LLM-generated summary."

    async def test_critique_score_initialised_to_zero(self) -> None:
        articles = [_make_article()]
        state = _make_state(enriched_articles=articles)
        result = await news_summary_agent(state)
        assert result["summaries"][0]["critique_score"] == 0.0


# ── CriticAgent ──────────────────────────────────────────────────────────────

class TestNewsCriticAgent:
    async def test_mock_critic_passes_with_score_085(self) -> None:
        articles = [_make_article(summary="A decent summary.")]
        state = _make_state(summaries=articles)
        result = await news_critic_agent(state, llm_critic=None)
        assert result["final_articles"][0]["critique_score"] == pytest.approx(0.85, abs=0.01)

    async def test_llm_critic_score_stored(self) -> None:
        mock_critic = AsyncMock()
        mock_critic.critique.return_value = (0.9, "great summary")
        articles = [_make_article(summary="Good summary.", content="Full content.")]
        state = _make_state(summaries=articles)
        result = await news_critic_agent(state, llm_critic=mock_critic)
        assert result["final_articles"][0]["critique_score"] == pytest.approx(0.9, abs=0.01)

    async def test_reflection_loop_retries_on_low_score(self) -> None:
        """When score < 0.8, the critic retries the summary."""
        mock_critic = AsyncMock()
        # First call returns low score, second call returns pass score
        mock_critic.critique.side_effect = [(0.5, "bad"), (0.9, "good")]

        mock_summarizer = AsyncMock()
        mock_summarizer.summarize.return_value = "Improved summary."

        articles = [_make_article(summary="Poor summary.", content="Content.")]
        state = _make_state(summaries=articles)
        result = await news_critic_agent(
            state,
            llm_critic=mock_critic,
            llm_summarizer=mock_summarizer,
            max_retries=2,
        )
        # summarizer should have been called once for the retry
        mock_summarizer.summarize.assert_awaited_once()
        assert result["final_articles"][0]["critique_score"] == pytest.approx(0.9, abs=0.01)

    async def test_empty_summaries_returns_empty_final(self) -> None:
        state = _make_state(summaries=[])
        result = await news_critic_agent(state)
        assert result["final_articles"] == []


# ── SynergyAgent ─────────────────────────────────────────────────────────────

class TestNewsSynergyAgent:
    async def test_high_relevance_articles_emit_signals(self) -> None:
        articles = [_make_article(action_relevance_score=0.9, title="Critical AI Security")]
        state = _make_state(final_articles=articles)
        result = await news_synergy_agent(state)
        assert len(result["action_signals"]) == 1
        assert result["action_signals"][0]["action_relevance_score"] == 0.9

    async def test_low_relevance_articles_excluded(self) -> None:
        articles = [_make_article(action_relevance_score=0.3)]
        state = _make_state(final_articles=articles)
        result = await news_synergy_agent(state)
        assert len(result["action_signals"]) == 0

    async def test_event_publisher_called_for_high_relevance(self) -> None:
        mock_publisher = AsyncMock()
        articles = [_make_article(action_relevance_score=0.95)]
        state = _make_state(final_articles=articles)
        await news_synergy_agent(state, event_publisher=mock_publisher)
        mock_publisher.assert_awaited_once()
        call_args = mock_publisher.call_args[0]
        assert call_args[0] == "news_action_signal"

    async def test_action_signal_has_required_fields(self) -> None:
        articles = [_make_article(action_relevance_score=0.85, title="Regulation Update")]
        state = _make_state(final_articles=articles)
        result = await news_synergy_agent(state)
        signal = result["action_signals"][0]
        assert "finding_id" in signal
        assert "title" in signal
        assert "suggested_task" in signal
        assert "action_relevance_score" in signal

    async def test_completed_is_set_true(self) -> None:
        state = _make_state(final_articles=[])
        result = await news_synergy_agent(state)
        assert result["completed"] is True

    async def test_publisher_error_does_not_abort(self) -> None:
        mock_publisher = AsyncMock(side_effect=RuntimeError("redis down"))
        articles = [_make_article(action_relevance_score=0.9)]
        state = _make_state(final_articles=articles)
        # Should not raise
        result = await news_synergy_agent(state, event_publisher=mock_publisher)
        assert len(result["action_signals"]) == 1
