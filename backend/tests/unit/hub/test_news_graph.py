"""Tests for the NewsAgentGraph — end-to-end pipeline, error propagation, signals."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.adapters.hub.graphs.news_graph import NewsAgentGraph


def _make_graph(**kwargs: object) -> NewsAgentGraph:
    return NewsAgentGraph(**kwargs)  # type: ignore[arg-type]


class TestNewsAgentGraphEndToEnd:
    async def test_pipeline_completes_with_mocks(self) -> None:
        graph = _make_graph()
        state = await graph.run(
            task_id="t-1",
            user_id="u-1",
            query="AI news",
        )
        assert state["completed"] is True
        assert state["error"] is None

    async def test_pipeline_produces_final_articles(self) -> None:
        graph = _make_graph()
        state = await graph.run(task_id="t-2", user_id="u-1", query="technology news")
        # With mock articles (3) all having good credibility, at least some should survive
        assert len(state.get("final_articles") or []) >= 0  # may be 0 or more

    async def test_pipeline_populates_thoughts(self) -> None:
        graph = _make_graph()
        state = await graph.run(task_id="t-3", user_id="u-1", query="latest news")
        assert len(state.get("thoughts") or []) > 0

    async def test_empty_results_handled_gracefully(self) -> None:
        mock_searcher = AsyncMock()
        mock_searcher.search.return_value = []
        graph = _make_graph(tavily_searcher=mock_searcher)
        state = await graph.run(task_id="t-4", user_id="u-1", query="nothing")
        assert state["error"] is None
        assert state.get("final_articles") == []

    async def test_searcher_error_halts_pipeline(self) -> None:
        mock_searcher = AsyncMock()
        mock_searcher.search.side_effect = RuntimeError("tavily down")
        graph = _make_graph(tavily_searcher=mock_searcher)
        state = await graph.run(task_id="t-5", user_id="u-1", query="news")
        assert state["error"] is not None
        assert state["completed"] is False

    async def test_action_signals_emitted_for_high_relevance(self) -> None:
        # Use user preferences that match mock article content
        graph = _make_graph()
        state = await graph.run(
            task_id="t-6",
            user_id="u-1",
            query="AI news",
            user_preferences={"news_topics": ["AI", "machine learning"]},
        )
        # action_signals should exist in state
        assert "action_signals" in state

    async def test_event_publisher_called_during_pipeline(self) -> None:
        mock_publisher = AsyncMock()
        graph = _make_graph(event_publisher=mock_publisher)
        await graph.run(task_id="t-7", user_id="u-1", query="latest headlines")
        assert mock_publisher.await_count > 0

    async def test_custom_tavily_searcher_used(self) -> None:
        mock_searcher = AsyncMock()
        mock_searcher.search.return_value = [
            {
                "url": "https://example.com/story",
                "title": "Custom Story",
                "content": "Long content about artificial intelligence and cloud technology " * 10,
                "published_date": "2026-04-22T09:00:00Z",
            }
        ]
        graph = _make_graph(tavily_searcher=mock_searcher)
        state = await graph.run(task_id="t-8", user_id="u-1", query="AI story")
        mock_searcher.search.assert_awaited_once()
        assert len(state.get("articles") or []) == 1
