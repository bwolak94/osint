"""Tests for HubState TypedDict and related structures."""

from __future__ import annotations

import pytest

from src.adapters.hub.state import HubMessage, HubState, RetrievedDoc, UserPreferences


class TestUserPreferences:
    def test_empty_preferences_allowed(self) -> None:
        prefs: UserPreferences = {}
        assert prefs == {}

    def test_full_preferences(self) -> None:
        prefs: UserPreferences = {
            "language": "pl",
            "news_topics": ["AI", "security"],
            "schedule_style": "balanced",
        }
        assert prefs["language"] == "pl"
        assert prefs["news_topics"] == ["AI", "security"]
        assert prefs["schedule_style"] == "balanced"


class TestHubMessage:
    def test_user_message(self) -> None:
        msg = HubMessage(role="user", content="What is AI?", name=None)
        assert msg["role"] == "user"
        assert msg["content"] == "What is AI?"
        assert msg["name"] is None

    def test_assistant_message_with_name(self) -> None:
        msg = HubMessage(role="assistant", content="Here is the plan", name="planner")
        assert msg["role"] == "assistant"
        assert msg["name"] == "planner"

    def test_tool_message(self) -> None:
        msg = HubMessage(role="tool", content="Search result", name="searcher")
        assert msg["role"] == "tool"


class TestRetrievedDoc:
    def test_full_doc(self) -> None:
        doc = RetrievedDoc(
            doc_id="doc-1",
            chunk_index=0,
            text="This is a document chunk.",
            source="https://example.com",
            score=0.92,
            tags=["ai", "research"],
        )
        assert doc["doc_id"] == "doc-1"
        assert doc["score"] == 0.92
        assert "ai" in doc["tags"]


class TestHubState:
    def test_minimal_state(self) -> None:
        state: HubState = {
            "task_id": "t-1",
            "user_id": "u-1",
            "query": "Hello",
            "current_agent": "supervisor",
            "completed": False,
        }
        assert state["task_id"] == "t-1"
        assert not state["completed"]

    def test_partial_update_merges(self) -> None:
        """dict.update() must not overwrite unrelated keys."""
        state: HubState = {
            "task_id": "t-1",
            "query": "test",
            "completed": False,
            "thoughts": ["first thought"],
        }
        update = {"current_agent": "searcher", "thoughts": ["first thought", "second thought"]}
        state.update(update)  # type: ignore[arg-type]
        assert state["task_id"] == "t-1"  # untouched
        assert state["current_agent"] == "searcher"
        assert len(state["thoughts"]) == 2

    def test_optional_fields_absent(self) -> None:
        """All fields optional — state without them is valid."""
        state: HubState = {}
        assert state.get("result") is None
        assert state.get("error") is None
        assert state.get("steps_taken") is None
