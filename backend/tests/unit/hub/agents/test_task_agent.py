"""Tests for the TaskAgent — intent parsing, CRUD, HITL on delete."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.adapters.hub.agents.task_agent import (
    _classify_intent,
    _extract_priority,
    _extract_title,
    task_agent,
)
from src.adapters.hub.state import HubState


def _make_state(query: str = "list my tasks", user_id: str = "u-1") -> HubState:
    return HubState(
        task_id="t-1",
        user_id=user_id,
        query=query,
        messages=[],
        thoughts=[],
        completed=False,
    )


class TestClassifyIntent:
    def test_list_intent(self) -> None:
        assert _classify_intent("list my tasks") == "list"
        assert _classify_intent("show all tasks") == "list"
        assert _classify_intent("what are my todos") == "list"

    def test_create_intent(self) -> None:
        assert _classify_intent("create new task: write tests") == "create"
        assert _classify_intent("add task: review PR") == "create"

    def test_update_intent(self) -> None:
        assert _classify_intent("update task status to done") == "update"
        assert _classify_intent("mark task as complete") == "update"

    def test_delete_intent(self) -> None:
        assert _classify_intent("delete the task") == "delete"
        assert _classify_intent("remove this task") == "delete"
        assert _classify_intent("cancel task abc") == "delete"

    def test_ambiguous_defaults_to_list(self) -> None:
        # backlog is a task keyword, so it should route to list
        assert _classify_intent("my backlog") == "list"


class TestExtractPriority:
    def test_urgent_maps_to_1(self) -> None:
        assert _extract_priority("urgent task needed") == 1

    def test_high_maps_to_2(self) -> None:
        assert _extract_priority("high priority item") == 2

    def test_low_maps_to_4(self) -> None:
        assert _extract_priority("low priority cleanup") == 4

    def test_default_priority_is_3(self) -> None:
        assert _extract_priority("create task: write docs") == 3


class TestExtractTitle:
    def test_strips_create_verb(self) -> None:
        title = _extract_title("create task: write unit tests")
        assert "write unit tests" in title

    def test_strips_add_verb(self) -> None:
        title = _extract_title("add review PR by Friday")
        assert "review PR by Friday" in title

    def test_returns_query_when_no_verb_matched(self) -> None:
        title = _extract_title("some random text")
        assert "some random text" in title


class TestTaskAgentDeleteAlwaysHITL:
    async def test_delete_requires_human_approval(self) -> None:
        state = _make_state(query="delete my task")
        result = await task_agent(state)
        assert result["requires_human_approval"] is True
        assert result["human_approval_pending"] is True
        assert result["current_agent"] == "awaiting_hitl"
        assert result.get("completed") is False

    async def test_remove_also_triggers_hitl(self) -> None:
        state = _make_state(query="remove task 123")
        result = await task_agent(state)
        assert result["requires_human_approval"] is True

    async def test_cancel_triggers_hitl(self) -> None:
        state = _make_state(query="cancel the backlog task")
        result = await task_agent(state)
        assert result["requires_human_approval"] is True


class TestTaskAgentMockMode:
    async def test_list_without_repository_returns_mock(self) -> None:
        state = _make_state(query="list my tasks")
        result = await task_agent(state, task_repository=None)
        assert result["completed"] is True
        assert result["error"] is None
        assert "mock" in result["result"].lower()

    async def test_create_without_repository_returns_mock(self) -> None:
        state = _make_state(query="create task: write docs")
        result = await task_agent(state, task_repository=None)
        assert result["completed"] is True
        assert result["error"] is None


class TestTaskAgentWithRepository:
    async def test_list_calls_repository(self) -> None:
        mock_repo = AsyncMock()
        mock_repo.list_tasks.return_value = [{"id": "1", "title": "Test task"}]
        state = _make_state(query="show all my tasks")
        result = await task_agent(state, task_repository=mock_repo)
        mock_repo.list_tasks.assert_awaited_once()
        assert "1 task" in result["result"]

    async def test_create_calls_repository(self) -> None:
        mock_repo = AsyncMock()
        mock_repo.create_task.return_value = {"id": "new-1", "title": "write docs"}
        state = _make_state(query="add task: write documentation")
        result = await task_agent(state, task_repository=mock_repo)
        mock_repo.create_task.assert_awaited_once()
        assert result["completed"] is True

    async def test_repository_error_sets_error_state(self) -> None:
        mock_repo = AsyncMock()
        mock_repo.list_tasks.side_effect = RuntimeError("db error")
        state = _make_state(query="list tasks")
        result = await task_agent(state, task_repository=mock_repo)
        assert result["error"] is not None
        assert "db error" in result["error"]
