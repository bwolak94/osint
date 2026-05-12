"""Tests for PlannerAgent — goal decomposition and HITL gating."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.adapters.hub.agents.planner import (
    _decompose_goal,
    _requires_approval,
    planner_agent,
)
from src.adapters.hub.state import HubState


def _make_state(query: str = "plan my week") -> HubState:
    return HubState(
        task_id="t-1",
        user_id="u-1",
        query=query,
        messages=[],
        thoughts=[],
        completed=False,
    )


class TestRequiresApproval:
    def test_delete_requires_approval(self) -> None:
        assert _requires_approval("delete all my tasks")

    def test_remove_requires_approval(self) -> None:
        assert _requires_approval("remove this event")

    def test_cancel_requires_approval(self) -> None:
        assert _requires_approval("cancel my appointment")

    def test_send_requires_approval(self) -> None:
        assert _requires_approval("send email to team")

    def test_normal_planning_no_approval(self) -> None:
        assert not _requires_approval("plan my week")
        assert not _requires_approval("organize my tasks")
        assert not _requires_approval("schedule my day")

    def test_case_insensitive(self) -> None:
        assert _requires_approval("DELETE everything")


class TestDecomposeGoal:
    def test_returns_list_of_strings(self) -> None:
        tasks = _decompose_goal("launch product")
        assert isinstance(tasks, list)
        assert len(tasks) >= 1
        assert all(isinstance(t, str) for t in tasks)

    def test_query_referenced_in_first_task(self) -> None:
        tasks = _decompose_goal("launch product")
        assert "launch product" in tasks[0]


class TestPlannerAgent:
    async def test_normal_query_completes(self) -> None:
        state = _make_state("plan my week")
        update = await planner_agent(state)
        assert update["completed"] is True
        assert update["current_agent"] == "done"
        assert update["result"] is not None
        assert update["error"] is None

    async def test_hitl_required_for_delete(self) -> None:
        state = _make_state("delete all my tasks")
        update = await planner_agent(state)
        assert update["requires_human_approval"] is True
        assert update["human_approval_pending"] is True
        assert update["current_agent"] == "awaiting_hitl"
        assert update["completed"] is False

    async def test_calendar_service_slots_in_plan(self) -> None:
        mock_cal = AsyncMock()
        mock_cal.get_free_slots.return_value = [
            {"start": "2026-04-22 10:00", "end": "2026-04-22 11:00"},
            {"start": "2026-04-22 14:00", "end": "2026-04-22 15:00"},
        ]
        state = _make_state("plan my week")
        update = await planner_agent(state, calendar_service=mock_cal)
        mock_cal.get_free_slots.assert_called_once()
        assert "Suggested time slots" in update["result"]

    async def test_calendar_service_error_degrades_gracefully(self) -> None:
        mock_cal = AsyncMock()
        mock_cal.get_free_slots.side_effect = ConnectionError("Calendar unavailable")
        state = _make_state("plan my week")
        update = await planner_agent(state, calendar_service=mock_cal)
        assert update["completed"] is True
        assert update["error"] is None
        assert any("unavailable" in t for t in update["thoughts"])

    async def test_no_calendar_service_still_produces_plan(self) -> None:
        state = _make_state("organize tasks")
        update = await planner_agent(state, calendar_service=None)
        assert update["completed"] is True
        assert "Proposed Plan" in update["result"]

    async def test_thoughts_include_decomposition(self) -> None:
        state = _make_state("plan my week")
        update = await planner_agent(state)
        assert any("decomposing" in t for t in update["thoughts"])

    async def test_assistant_message_appended(self) -> None:
        state = _make_state("plan my week")
        update = await planner_agent(state)
        msgs = update["messages"]
        assert len(msgs) == 1
        assert msgs[0]["name"] == "planner"

    async def test_result_metadata_contains_sub_tasks(self) -> None:
        state = _make_state("plan my week")
        update = await planner_agent(state)
        assert "sub_tasks" in update["result_metadata"]
        assert len(update["result_metadata"]["sub_tasks"]) >= 1

    async def test_hitl_thought_appended(self) -> None:
        state = _make_state("delete all my tasks")
        update = await planner_agent(state)
        assert any("human approval" in t for t in update["thoughts"])
