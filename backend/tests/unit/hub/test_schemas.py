"""Tests for Hub API Pydantic schemas — validation, defaults, constraints."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.api.v1.hub.schemas import (
    AgentRunRequest,
    AgentRunResponse,
    AgentStatusResponse,
    HitlApprovalRequest,
    HitlApprovalResponse,
)


class TestAgentRunRequest:
    def test_valid_request(self) -> None:
        req = AgentRunRequest(query="find AI news")
        assert req.query == "find AI news"
        assert req.module == "chat"

    def test_empty_query_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AgentRunRequest(query="")

    def test_too_long_query_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AgentRunRequest(query="x" * 4097)

    def test_valid_modules(self) -> None:
        for module in ("news", "calendar", "tasks", "knowledge", "chat"):
            req = AgentRunRequest(query="test", module=module)
            assert req.module == module

    def test_invalid_module_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AgentRunRequest(query="test", module="invalid")

    def test_user_preferences_defaults_empty(self) -> None:
        req = AgentRunRequest(query="test")
        assert req.user_preferences == {}

    def test_user_preferences_accepted(self) -> None:
        req = AgentRunRequest(
            query="test",
            user_preferences={"language": "pl"},
        )
        assert req.user_preferences["language"] == "pl"


class TestAgentRunResponse:
    def test_valid_response(self) -> None:
        resp = AgentRunResponse(
            task_id="abc-123",
            stream_url="ws://hub/stream",
        )
        assert resp.task_id == "abc-123"
        assert resp.status == "queued"

    def test_status_locked_to_queued(self) -> None:
        resp = AgentRunResponse(task_id="x", stream_url="ws://y")
        assert resp.status == "queued"


class TestAgentStatusResponse:
    def test_valid_running_status(self) -> None:
        resp = AgentStatusResponse(task_id="t-1", status="running")
        assert resp.status == "running"
        assert resp.result is None
        assert resp.error is None
        assert resp.thoughts == []

    def test_completed_with_result(self) -> None:
        resp = AgentStatusResponse(
            task_id="t-1",
            status="completed",
            result="Here is the answer",
            thoughts=["thought 1"],
        )
        assert resp.result == "Here is the answer"
        assert len(resp.thoughts) == 1

    def test_failed_with_error(self) -> None:
        resp = AgentStatusResponse(task_id="t-1", status="failed", error="boom")
        assert resp.error == "boom"


class TestHitlApprovalRequest:
    def test_approved_true(self) -> None:
        req = HitlApprovalRequest(approved=True)
        assert req.approved is True

    def test_approved_false(self) -> None:
        req = HitlApprovalRequest(approved=False)
        assert req.approved is False

    def test_missing_approved_rejected(self) -> None:
        with pytest.raises(ValidationError):
            HitlApprovalRequest()  # type: ignore[call-arg]


class TestHitlApprovalResponse:
    def test_resumed_status(self) -> None:
        resp = HitlApprovalResponse(task_id="t-1", approved=True, status="resumed")
        assert resp.status == "resumed"

    def test_aborted_status(self) -> None:
        resp = HitlApprovalResponse(task_id="t-1", approved=False, status="aborted")
        assert resp.status == "aborted"
