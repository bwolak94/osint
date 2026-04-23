"""Tests for the CalendarAgent — slot proposals, overload detection, HITL on writes."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.adapters.hub.agents.calendar_agent import (
    _is_write_intent,
    _parse_duration,
    calendar_agent,
)
from src.adapters.hub.state import HubState
from src.adapters.calendar.cognitive_load import CognitiveLoadModel, TimeSlot


def _make_state(query: str = "show my free slots") -> HubState:
    return HubState(
        task_id="t-cal",
        user_id="u-1",
        query=query,
        messages=[],
        thoughts=[],
        completed=False,
    )


class TestIsWriteIntent:
    def test_create_event_is_write(self) -> None:
        assert _is_write_intent("create a meeting with John")

    def test_book_is_write(self) -> None:
        assert _is_write_intent("book a slot for tomorrow")

    def test_schedule_appointment_is_write(self) -> None:
        assert _is_write_intent("schedule a new appointment")

    def test_show_free_slots_is_read(self) -> None:
        assert not _is_write_intent("show my free slots")

    def test_list_events_is_read(self) -> None:
        assert not _is_write_intent("list available times")


class TestParseDuration:
    def test_parses_hours(self) -> None:
        assert _parse_duration("schedule a 2 hour meeting") == 120

    def test_parses_minutes(self) -> None:
        assert _parse_duration("30 minute standup") == 30

    def test_defaults_to_60_minutes(self) -> None:
        assert _parse_duration("find me a slot") == 60


class TestCalendarAgentHITL:
    async def test_write_intent_triggers_hitl(self) -> None:
        state = _make_state(query="create a meeting tomorrow at 10am")
        result = await calendar_agent(state)
        assert result["requires_human_approval"] is True
        assert result["human_approval_pending"] is True
        assert result["current_agent"] == "awaiting_hitl"

    async def test_book_triggers_hitl(self) -> None:
        state = _make_state(query="book a 1 hour slot")
        result = await calendar_agent(state)
        assert result["requires_human_approval"] is True

    async def test_approved_write_skips_hitl(self) -> None:
        state = _make_state(query="create a meeting")
        state["hitl_already_approved"] = True
        result = await calendar_agent(state)
        assert result["requires_human_approval"] is False
        assert result["completed"] is True


class TestCalendarAgentSlotFinding:
    async def test_read_query_returns_slot_proposal(self) -> None:
        mock_calendar = AsyncMock()
        mock_calendar.list_events.return_value = []
        mock_calendar.get_free_slots.return_value = [
            {"start": "2026-04-23T09:00:00Z", "end": "2026-04-23T10:00:00Z"}
        ]
        state = _make_state(query="find free time for a 1 hour meeting")
        result = await calendar_agent(state, calendar_service=mock_calendar)
        assert result["completed"] is True
        assert result["result"] is not None
        assert "2026-04-23" in result["result"]

    async def test_cognitive_load_model_used_when_provided(self) -> None:
        mock_model = AsyncMock()
        mock_model.find_best_slots.return_value = [
            TimeSlot(start="2026-04-23T09:00:00Z", end="2026-04-23T10:00:00Z", score=0.95)
        ]
        state = _make_state(query="suggest best time for a meeting")
        result = await calendar_agent(state, cognitive_load_model=mock_model)
        mock_model.find_best_slots.assert_awaited_once()
        assert "0.95" in result["result"]

    async def test_no_slots_returns_graceful_message(self) -> None:
        state = _make_state(query="find free slots")
        result = await calendar_agent(state)  # no calendar_service or model
        assert result["completed"] is True
        assert result["error"] is None


class TestCognitiveLoadModel:
    async def test_peak_hours_score_high(self) -> None:
        model = CognitiveLoadModel()
        score_9am = await model.score_slot("2026-04-21T09:00:00+00:00")  # Monday 9am
        score_3am = await model.score_slot("2026-04-21T03:00:00+00:00")  # Monday 3am
        assert score_9am > score_3am

    async def test_score_bounded_0_to_1(self) -> None:
        model = CognitiveLoadModel()
        for hour in [0, 9, 10, 14, 23]:
            score = await model.score_slot(f"2026-04-21T{hour:02d}:00:00+00:00")
            assert 0.0 <= score <= 1.0

    async def test_find_best_slots_returns_n_slots(self) -> None:
        model = CognitiveLoadModel()
        slots = await model.find_best_slots(duration_minutes=60, n=3)
        assert len(slots) == 3

    async def test_find_best_slots_sorted_by_score_desc(self) -> None:
        model = CognitiveLoadModel()
        slots = await model.find_best_slots(duration_minutes=60, n=5)
        scores = [s["score"] for s in slots]
        assert scores == sorted(scores, reverse=True)
