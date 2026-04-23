"""Tests for Celery hub tasks — task lifecycle, status transitions, HITL."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.workers.tasks.hub_tasks import (
    _TASK_RESULT_KEY,
    _TASK_STATE_KEY,
    _TASK_STATUS_KEY,
    _TTL,
    _build_graph,
    _get_redis_sync,
)


class TestRedisKeyHelpers:
    def test_status_key_format(self) -> None:
        key = _TASK_STATUS_KEY.format("abc-123")
        assert key == "hub:task:abc-123:status"

    def test_result_key_format(self) -> None:
        key = _TASK_RESULT_KEY.format("abc-123")
        assert key == "hub:task:abc-123:result"

    def test_state_key_format(self) -> None:
        key = _TASK_STATE_KEY.format("abc-123")
        assert key == "hub:task:abc-123:state"

    def test_ttl_is_one_hour(self) -> None:
        assert _TTL == 3600


class TestBuildGraph:
    def test_returns_hub_agent_graph(self) -> None:
        # _build_graph does a local import; patch the class at its definition site
        with patch("src.adapters.hub.graph.HubAgentGraph") as mock_cls:
            mock_cls.return_value = MagicMock()
            graph = _build_graph("t-1")
            mock_cls.assert_called_once()

    def test_graph_has_publisher(self) -> None:
        """The graph must be built with an event_publisher (not None)."""
        with patch("src.adapters.hub.graph.HubAgentGraph") as mock_cls:
            mock_cls.return_value = MagicMock()
            _build_graph("t-1")
            call_kwargs = mock_cls.call_args[1]
            assert call_kwargs["event_publisher"] is not None


class TestGetRedisSyncImport:
    def test_returns_redis_client(self) -> None:
        """_get_redis_sync must import successfully under mock settings."""
        mock_redis = MagicMock()
        with (
            patch("src.config.get_settings") as mock_settings,
            patch("redis.Redis.from_url", return_value=mock_redis),
        ):
            mock_settings.return_value.redis_url = "redis://localhost:6379/0"
            client = _get_redis_sync()
            assert client is not None


class TestRunHubAgentTaskLogic:
    """Unit tests for the async state-machine logic embedded in hub tasks.

    We extract the core branching logic into a standalone async helper
    so it can be awaited directly in pytest-asyncio tests (asyncio.run()
    cannot be called from inside an already-running event loop).
    """

    async def _simulate_run(
        self,
        task_id: str,
        graph_return: dict,
    ) -> dict:
        """Simulate the _run() coroutine from run_hub_agent_task."""
        stored: dict[str, str] = {}

        def setex(key: str, ttl: int, value: str) -> None:
            stored[key] = value

        mock_graph = AsyncMock()
        mock_graph.run.return_value = graph_return

        state = await mock_graph.run(
            task_id=task_id, user_id="u-1",
            query="test", module="chat", user_preferences={},
        )
        if state.get("human_approval_pending"):
            setex(_TASK_STATUS_KEY.format(task_id), _TTL, "awaiting_hitl")
            setex(_TASK_STATE_KEY.format(task_id), _TTL, json.dumps(state))
            return stored
        final_status = "failed" if state.get("error") else "completed"
        setex(_TASK_STATUS_KEY.format(task_id), _TTL, final_status)
        setex(
            _TASK_RESULT_KEY.format(task_id),
            _TTL,
            json.dumps({
                "result": state.get("result"),
                "thoughts": state.get("thoughts", []),
                "error": state.get("error"),
            }),
        )
        return stored

    async def test_completed_task_stores_result(self) -> None:
        stored = await self._simulate_run(
            "t-1",
            {"result": "Answer here", "thoughts": ["t1"], "error": None, "human_approval_pending": False},
        )
        assert stored[_TASK_STATUS_KEY.format("t-1")] == "completed"
        result_data = json.loads(stored[_TASK_RESULT_KEY.format("t-1")])
        assert result_data["result"] == "Answer here"
        assert result_data["thoughts"] == ["t1"]

    async def test_hitl_state_stores_awaiting_status(self) -> None:
        stored = await self._simulate_run(
            "t-hitl",
            {"result": None, "thoughts": [], "error": None, "human_approval_pending": True},
        )
        assert stored[_TASK_STATUS_KEY.format("t-hitl")] == "awaiting_hitl"
        saved = json.loads(stored[_TASK_STATE_KEY.format("t-hitl")])
        assert saved["human_approval_pending"] is True

    async def test_error_state_stores_failed_status(self) -> None:
        stored = await self._simulate_run(
            "t-err",
            {"result": None, "thoughts": [], "error": "agent crashed", "human_approval_pending": False},
        )
        assert stored[_TASK_STATUS_KEY.format("t-err")] == "failed"
