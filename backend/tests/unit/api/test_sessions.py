"""Tests for session management endpoints."""

import pytest


class TestSessionEndpoints:
    """Tests for the session management API."""

    async def test_list_sessions_returns_empty(self):
        """List sessions should return empty when no sessions exist."""
        from src.api.v1.auth.sessions import list_sessions

        mock_user = {"sub": "test-user-id"}
        result = await list_sessions(current_user=mock_user)
        assert result.sessions == []
        assert result.total == 0

    async def test_revoke_session(self):
        """Revoke session should return success."""
        from src.api.v1.auth.sessions import revoke_session

        mock_user = {"sub": "test-user-id"}
        result = await revoke_session(session_id="test-session", current_user=mock_user)
        assert result["status"] == "revoked"

    async def test_revoke_all_sessions(self):
        """Revoke all should return success."""
        from src.api.v1.auth.sessions import revoke_all_sessions

        mock_user = {"sub": "test-user-id"}
        result = await revoke_all_sessions(current_user=mock_user)
        assert result["status"] == "all_revoked"
