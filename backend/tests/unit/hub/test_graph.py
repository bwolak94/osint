"""Tests for HubAgentGraph — orchestration, routing, HITL, error handling."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.adapters.hub.graph import HubAgentGraph
from src.adapters.hub.state import HubState


def _make_graph(**kwargs: object) -> HubAgentGraph:
    return HubAgentGraph(
        retriever=None,
        calendar_service=None,
        event_publisher=None,
        **kwargs,  # type: ignore[arg-type]
    )


class TestHubAgentGraphRun:
    async def test_searcher_query_completes(self) -> None:
        graph = _make_graph()
        state = await graph.run(
            task_id="t-1",
            user_id="u-1",
            query="find AI news",
        )
        assert state["completed"] is True
        assert state["error"] is None
        assert state["result"] is not None
        assert state["current_agent"] == "done"

    async def test_planner_query_completes(self) -> None:
        graph = _make_graph()
        state = await graph.run(
            task_id="t-2",
            user_id="u-1",
            query="plan my week",
        )
        assert state["completed"] is True
        assert state["error"] is None

    async def test_hitl_pauses_execution(self) -> None:
        graph = _make_graph()
        state = await graph.run(
            task_id="t-3",
            user_id="u-1",
            query="delete all my tasks",
        )
        assert state["completed"] is False
        assert state["human_approval_pending"] is True
        assert state["current_agent"] == "awaiting_hitl"

    async def test_empty_query_aborts(self) -> None:
        graph = _make_graph()
        state = await graph.run(task_id="t-4", user_id="u-1", query="")
        assert state["completed"] is True
        assert state["error"] is not None

    async def test_state_initialised_with_defaults(self) -> None:
        graph = _make_graph()
        state = await graph.run(task_id="t-5", user_id="u-1", query="hello")
        assert state["task_id"] == "t-5"
        assert state["user_id"] == "u-1"
        assert isinstance(state["messages"], list)
        assert isinstance(state["thoughts"], list)
        assert isinstance(state["retrieved_docs"], list)

    async def test_steps_taken_increments(self) -> None:
        graph = _make_graph()
        state = await graph.run(task_id="t-6", user_id="u-1", query="find news")
        # supervisor + searcher = 2 steps minimum
        assert state["steps_taken"] >= 2

    async def test_user_preferences_stored_in_state(self) -> None:
        graph = _make_graph()
        state = await graph.run(
            task_id="t-7",
            user_id="u-1",
            query="hello",
            user_preferences={"language": "pl"},
        )
        assert state["user_preferences"]["language"] == "pl"

    async def test_event_publisher_called_on_start_and_done(self) -> None:
        publisher = AsyncMock()
        graph = HubAgentGraph(event_publisher=publisher)
        await graph.run(task_id="t-8", user_id="u-1", query="find news")
        # Check graph_start and graph_done events were published
        event_types = [call.args[1]["type"] for call in publisher.call_args_list]
        assert "graph_start" in event_types
        assert "graph_done" in event_types

    async def test_publisher_failure_does_not_abort(self) -> None:
        """A broken event publisher must never crash the agent pipeline."""
        async def broken_publisher(task_id: str, event: dict) -> None:
            raise RuntimeError("Redis unavailable")

        graph = HubAgentGraph(event_publisher=broken_publisher)
        state = await graph.run(task_id="t-9", user_id="u-1", query="find news")
        assert state["completed"] is True  # pipeline completed despite publisher failure

    async def test_unknown_node_sets_error(self) -> None:
        graph = _make_graph()
        # Inject directly into _nodes so the patch is effective
        async def bad_supervisor(state: dict) -> dict:
            return {"current_agent": "nonexistent_node", "thoughts": [], "messages": []}
        graph._nodes["supervisor"] = bad_supervisor
        state = await graph.run(task_id="t-10", user_id="u-1", query="hello")
        assert state["error"] is not None
        assert "Unknown agent node" in state["error"]

    async def test_node_exception_sets_error(self) -> None:
        graph = _make_graph()
        async def exploding_supervisor(state: dict) -> dict:
            raise RuntimeError("boom")
        graph._nodes["supervisor"] = exploding_supervisor
        state = await graph.run(task_id="t-11", user_id="u-1", query="hello")
        assert state["completed"] is True
        assert "boom" in state["error"]

    async def test_max_steps_prevents_infinite_loop(self) -> None:
        """Graph must not loop forever if an agent never sets completed."""
        graph = _make_graph()
        # Make supervisor always route to itself — graph must terminate at _MAX_STEPS
        async def looping_supervisor(state: dict) -> dict:
            return {"current_agent": "supervisor", "thoughts": [], "messages": []}
        graph._nodes["supervisor"] = looping_supervisor
        state = await graph.run(task_id="t-12", user_id="u-1", query="loop")
        assert state["steps_taken"] >= 10


class TestHubAgentGraphResumeAfterHitl:
    async def _paused_state(self) -> HubState:
        """Helper: run a query that triggers HITL and return the paused state."""
        graph = _make_graph()
        return await graph.run(
            task_id="hitl-1",
            user_id="u-1",
            query="delete all my tasks",
        )

    async def test_rejection_aborts_gracefully(self) -> None:
        state = await self._paused_state()
        graph = _make_graph()
        final = await graph.resume_after_hitl(state=state, approved=False)
        assert final["completed"] is True
        assert "cancelled" in final["result"].lower()
        assert final["human_approval_pending"] is False
        assert final["current_agent"] == "done"

    async def test_approval_resumes_execution(self) -> None:
        state = await self._paused_state()
        graph = _make_graph()
        final = await graph.resume_after_hitl(state=state, approved=True)
        assert final["completed"] is True
        assert final["human_approval_pending"] is False

    async def test_rejection_publisher_called(self) -> None:
        state = await self._paused_state()
        publisher = AsyncMock()
        graph = HubAgentGraph(event_publisher=publisher)
        await graph.resume_after_hitl(state=state, approved=False)
        event_types = [call.args[1]["type"] for call in publisher.call_args_list]
        assert "hitl_rejected" in event_types

    async def test_approval_publisher_called(self) -> None:
        state = await self._paused_state()
        publisher = AsyncMock()
        graph = HubAgentGraph(event_publisher=publisher)
        await graph.resume_after_hitl(state=state, approved=True)
        event_types = [call.args[1]["type"] for call in publisher.call_args_list]
        assert "hitl_approved" in event_types
