"""Tests for the Hub API router endpoints using FastAPI TestClient."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.v1.hub.router import router
from src.api.v1.hub.schemas import AgentRunResponse, AgentStatusResponse


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(_make_app())


@pytest.fixture()
def mock_redis() -> AsyncMock:
    redis = AsyncMock()
    redis.setex = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    return redis


class TestPostAgentRun:
    def test_returns_202_with_task_id(self, client: TestClient) -> None:
        with (
            patch("src.api.v1.hub.router._get_redis") as mock_get_redis,
            patch("src.api.v1.hub.router.run_hub_agent_task") as mock_task,
        ):
            mock_redis = AsyncMock()
            mock_redis.setex = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_task.apply_async = MagicMock()

            resp = client.post(
                "/api/v1/hub/agent/run",
                json={"query": "find AI news"},
            )

        assert resp.status_code == 202
        data = resp.json()
        assert "task_id" in data
        assert data["status"] == "queued"
        assert "stream_url" in data

    def test_empty_query_rejected(self, client: TestClient) -> None:
        resp = client.post("/api/v1/hub/agent/run", json={"query": ""})
        assert resp.status_code == 422

    def test_invalid_module_rejected(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/hub/agent/run",
            json={"query": "test", "module": "invalid_module"},
        )
        assert resp.status_code == 422

    def test_celery_task_enqueued(self, client: TestClient) -> None:
        with (
            patch("src.api.v1.hub.router._get_redis") as mock_get_redis,
            patch("src.api.v1.hub.router.run_hub_agent_task") as mock_task,
        ):
            mock_redis = AsyncMock()
            mock_redis.setex = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_task.apply_async = MagicMock()

            client.post("/api/v1/hub/agent/run", json={"query": "plan my week"})
            mock_task.apply_async.assert_called_once()

    def test_redis_status_set_to_queued(self, client: TestClient) -> None:
        with (
            patch("src.api.v1.hub.router._get_redis") as mock_get_redis,
            patch("src.api.v1.hub.router.run_hub_agent_task") as mock_task,
        ):
            mock_redis = AsyncMock()
            mock_redis.setex = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_task.apply_async = MagicMock()

            client.post("/api/v1/hub/agent/run", json={"query": "test"})

            mock_redis.setex.assert_called_once()
            args = mock_redis.setex.call_args[0]
            assert "queued" in args


class TestGetTaskStatus:
    def test_returns_404_when_task_not_found(self, client: TestClient) -> None:
        with patch("src.api.v1.hub.router._get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_redis.get = AsyncMock(return_value=None)
            mock_get_redis.return_value = mock_redis

            resp = client.get("/api/v1/hub/tasks/nonexistent")
        assert resp.status_code == 404

    def test_returns_status_when_found(self, client: TestClient) -> None:
        with patch("src.api.v1.hub.router._get_redis") as mock_get_redis:
            mock_redis = AsyncMock()

            async def mock_get(key: str) -> bytes | None:
                if "status" in key:
                    return b"running"
                return None  # no result yet

            mock_redis.get = mock_get
            mock_get_redis.return_value = mock_redis

            resp = client.get("/api/v1/hub/tasks/t-123")
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == "t-123"
        assert data["status"] == "running"

    def test_returns_result_when_completed(self, client: TestClient) -> None:
        result_payload = json.dumps({
            "result": "Here is the answer",
            "thoughts": ["t1"],
            "error": None,
        })

        with patch("src.api.v1.hub.router._get_redis") as mock_get_redis:
            mock_redis = AsyncMock()

            async def mock_get(key: str) -> bytes | None:
                if "status" in key:
                    return b"completed"
                if "result" in key:
                    return result_payload.encode()
                return None

            mock_redis.get = mock_get
            mock_get_redis.return_value = mock_redis

            resp = client.get("/api/v1/hub/tasks/t-done")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["result"] == "Here is the answer"
        assert data["thoughts"] == ["t1"]


class TestPostHitlApproval:
    def test_returns_404_for_unknown_task(self, client: TestClient) -> None:
        with patch("src.api.v1.hub.router._get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_redis.get = AsyncMock(return_value=None)
            mock_get_redis.return_value = mock_redis

            resp = client.post(
                "/api/v1/hub/tasks/unknown/approve",
                json={"approved": True},
            )
        assert resp.status_code == 404

    def test_returns_409_when_not_awaiting_hitl(self, client: TestClient) -> None:
        with patch("src.api.v1.hub.router._get_redis") as mock_get_redis:
            mock_redis = AsyncMock()
            mock_redis.get = AsyncMock(return_value=b"running")
            mock_get_redis.return_value = mock_redis

            resp = client.post(
                "/api/v1/hub/tasks/t-1/approve",
                json={"approved": True},
            )
        assert resp.status_code == 409

    def test_approval_enqueues_resume_task(self, client: TestClient) -> None:
        saved_state = json.dumps({"task_id": "t-1", "human_approval_pending": True})

        with (
            patch("src.api.v1.hub.router._get_redis") as mock_get_redis,
            patch("src.api.v1.hub.router.resume_hub_agent_task") as mock_resume,
        ):
            mock_redis = AsyncMock()

            async def mock_get(key: str) -> bytes | None:
                if "status" in key:
                    return b"awaiting_hitl"
                if "state" in key:
                    return saved_state.encode()
                return None

            mock_redis.get = mock_get
            mock_get_redis.return_value = mock_redis
            mock_resume.apply_async = MagicMock()

            resp = client.post(
                "/api/v1/hub/tasks/t-1/approve",
                json={"approved": True},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["approved"] is True
        assert data["status"] == "resumed"
        mock_resume.apply_async.assert_called_once()

    def test_rejection_response_is_aborted(self, client: TestClient) -> None:
        saved_state = json.dumps({"task_id": "t-1", "human_approval_pending": True})

        with (
            patch("src.api.v1.hub.router._get_redis") as mock_get_redis,
            patch("src.api.v1.hub.router.resume_hub_agent_task") as mock_resume,
        ):
            mock_redis = AsyncMock()

            async def mock_get(key: str) -> bytes | None:
                if "status" in key:
                    return b"awaiting_hitl"
                if "state" in key:
                    return saved_state.encode()
                return None

            mock_redis.get = mock_get
            mock_get_redis.return_value = mock_redis
            mock_resume.apply_async = MagicMock()

            resp = client.post(
                "/api/v1/hub/tasks/t-1/approve",
                json={"approved": False},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["approved"] is False
        assert data["status"] == "aborted"
