"""Tests for SearcherAgent — document retrieval and answer synthesis."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.adapters.hub.agents.searcher import (
    _build_answer,
    _format_context,
    searcher_agent,
)
from src.adapters.hub.state import HubState, RetrievedDoc


def _make_doc(score: float = 0.85, text: str = "Some content") -> RetrievedDoc:
    return RetrievedDoc(
        doc_id="doc-1",
        chunk_index=0,
        text=text,
        source="https://example.com",
        score=score,
        tags=["test"],
    )


def _make_state(query: str = "test query") -> HubState:
    return HubState(
        task_id="t-1",
        user_id="u-1",
        query=query,
        messages=[],
        thoughts=[],
        completed=False,
    )


class TestFormatContext:
    def test_empty_docs_returns_placeholder(self) -> None:
        result = _format_context([])
        assert "No relevant documents" in result

    def test_single_doc_formatted(self) -> None:
        doc = _make_doc()
        result = _format_context([doc])
        assert "[1]" in result
        assert "https://example.com" in result
        assert "Some content" in result

    def test_multiple_docs_indexed(self) -> None:
        docs = [_make_doc(text=f"Content {i}") for i in range(3)]
        result = _format_context(docs)
        assert "[1]" in result
        assert "[2]" in result
        assert "[3]" in result


class TestBuildAnswer:
    def test_answer_contains_query(self) -> None:
        answer = _build_answer("What is AI?", "AI is...")
        assert "What is AI?" in answer

    def test_answer_contains_context(self) -> None:
        answer = _build_answer("query", "Some important context")
        assert "Some important context" in answer


class TestSearcherAgent:
    async def test_no_retriever_returns_result(self) -> None:
        state = _make_state("find AI papers")
        update = await searcher_agent(state, retriever=None)
        assert update["completed"] is True
        assert update["result"] is not None
        assert update["current_agent"] == "done"
        assert update["error"] is None

    async def test_retriever_injected_results_included(self) -> None:
        mock_retriever = AsyncMock()
        mock_retriever.retrieve.return_value = [
            _make_doc(score=0.9, text="Retrieved content")
        ]
        state = _make_state("find something")
        update = await searcher_agent(state, retriever=mock_retriever)
        mock_retriever.retrieve.assert_called_once_with("find something", top_k=5)
        assert len(update["retrieved_docs"]) == 1
        assert "Retrieved content" in update["result"]

    async def test_low_score_docs_filtered(self) -> None:
        """Docs with score < 0.60 must be excluded."""
        mock_retriever = AsyncMock()
        mock_retriever.retrieve.return_value = [
            _make_doc(score=0.3, text="Low score doc"),
            _make_doc(score=0.85, text="High score doc"),
        ]
        state = _make_state("query")
        update = await searcher_agent(state, retriever=mock_retriever)
        assert len(update["retrieved_docs"]) == 1
        assert update["retrieved_docs"][0]["score"] == 0.85

    async def test_retriever_error_degrades_gracefully(self) -> None:
        """A retriever exception must not abort the task."""
        mock_retriever = AsyncMock()
        mock_retriever.retrieve.side_effect = ConnectionError("Qdrant unavailable")
        state = _make_state("query")
        update = await searcher_agent(state, retriever=mock_retriever)
        assert update["completed"] is True
        assert update["error"] is None  # degraded, not failed
        assert len(update["retrieved_docs"]) == 0
        # A thought about the error should be appended
        assert any("error" in t.lower() for t in update["thoughts"])

    async def test_thoughts_updated(self) -> None:
        state = _make_state("query")
        update = await searcher_agent(state, retriever=None)
        assert len(update["thoughts"]) >= 2

    async def test_assistant_message_appended(self) -> None:
        state = _make_state("query")
        update = await searcher_agent(state, retriever=None)
        msgs = update["messages"]
        assert len(msgs) == 1
        assert msgs[0]["name"] == "searcher"
        assert msgs[0]["role"] == "assistant"

    async def test_result_metadata_contains_agent(self) -> None:
        state = _make_state("query")
        update = await searcher_agent(state, retriever=None)
        assert update["result_metadata"]["agent"] == "searcher"

    async def test_preserves_existing_thoughts(self) -> None:
        state = _make_state("query")
        state["thoughts"] = ["pre-existing"]
        update = await searcher_agent(state, retriever=None)
        assert update["thoughts"][0] == "pre-existing"
