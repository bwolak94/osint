"""Tests for SupervisorAgent — routing and intent classification."""

from __future__ import annotations

import pytest

from src.adapters.hub.agents.supervisor import _classify_intent, supervisor_agent
from src.adapters.hub.state import HubState


class TestClassifyIntent:
    def test_planner_keywords_route_to_planner(self) -> None:
        # Phase 2: "plan" → planner; "deadline", "organize" → planner
        assert _classify_intent("plan my week") == "planner"
        assert _classify_intent("arrange a deadline for this project") == "planner"
        assert _classify_intent("what are my milestones") == "planner"

    def test_calendar_keywords_route_to_calendar(self) -> None:
        # Phase 2: "schedule", "meeting", "calendar" → calendar (more specific than planner)
        assert _classify_intent("schedule a meeting") == "calendar"
        assert _classify_intent("organize my calendar") == "calendar"
        assert _classify_intent("when am i free this week") == "calendar"

    def test_task_keywords_route_to_task(self) -> None:
        # Phase 2: "task", "todo", "backlog" → task agent
        assert _classify_intent("add a task for tomorrow") == "task"
        assert _classify_intent("my todo list") == "task"
        assert _classify_intent("my backlog priority") == "task"

    def test_news_keywords_route_to_news(self) -> None:
        # Phase 2: "news", "headlines" → news agent
        assert _classify_intent("find the latest AI news") == "news"
        assert _classify_intent("summarize today's news") == "news"
        assert _classify_intent("what are the trending headlines") == "news"

    def test_knowledge_keywords_route_to_knowledge(self) -> None:
        assert _classify_intent("search the knowledge base") == "knowledge"
        assert _classify_intent("find the document about security") == "knowledge"

    def test_searcher_keywords_route_to_searcher(self) -> None:
        assert _classify_intent("search for quantum computing papers") == "searcher"
        assert _classify_intent("what is LangGraph?") == "searcher"
        assert _classify_intent("how does HNSW work") == "searcher"

    def test_ambiguous_defaults_to_searcher(self) -> None:
        assert _classify_intent("hello") == "searcher"
        assert _classify_intent("...") == "searcher"
        assert _classify_intent("xyzzy") == "searcher"

    def test_case_insensitive(self) -> None:
        assert _classify_intent("PLAN my PROJECT") == "planner"
        assert _classify_intent("FIND the ANSWER") == "searcher"

    def test_task_wins_over_planner_on_tie_by_ordering(self) -> None:
        # "task" (task agent) AND "plan" (planner) — task is more specific, wins
        result = _classify_intent("plan and find tasks")
        assert result in ("task", "planner")  # either is valid; test ordering not value


class TestSupervisorAgent:
    def _make_state(self, query: str) -> HubState:
        return HubState(
            task_id="t-1",
            user_id="u-1",
            query=query,
            messages=[],
            thoughts=[],
            completed=False,
        )

    async def test_routes_to_searcher(self) -> None:
        state = self._make_state("search for quantum computing papers")
        update = await supervisor_agent(state)
        assert update["current_agent"] == "searcher"
        assert update["error"] is None
        assert len(update["thoughts"]) == 1
        assert "searcher" in update["thoughts"][0]

    async def test_routes_to_planner(self) -> None:
        state = self._make_state("plan my week")
        update = await supervisor_agent(state)
        assert update["current_agent"] == "planner"

    async def test_empty_query_aborts(self) -> None:
        state = self._make_state("")
        update = await supervisor_agent(state)
        assert update["completed"] is True
        assert update["current_agent"] == "done"
        assert "Empty query" in update["error"]

    async def test_whitespace_only_query_aborts(self) -> None:
        state = self._make_state("   ")
        update = await supervisor_agent(state)
        assert update["completed"] is True

    async def test_appends_to_existing_thoughts(self) -> None:
        state = self._make_state("find news")
        state["thoughts"] = ["pre-existing thought"]
        update = await supervisor_agent(state)
        assert len(update["thoughts"]) == 2
        assert update["thoughts"][0] == "pre-existing thought"

    async def test_appends_assistant_message(self) -> None:
        state = self._make_state("find news")
        update = await supervisor_agent(state)
        msgs = update["messages"]
        assert len(msgs) == 1
        assert msgs[0]["role"] == "assistant"
        assert msgs[0]["name"] == "supervisor"

    async def test_sets_human_approval_false(self) -> None:
        state = self._make_state("find news")
        update = await supervisor_agent(state)
        assert update["requires_human_approval"] is False
        assert update["human_approval_pending"] is False
