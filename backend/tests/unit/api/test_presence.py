"""Tests for presence endpoints."""

import pytest
from unittest.mock import MagicMock


class TestPresenceEndpoints:
    @pytest.mark.asyncio
    async def test_heartbeat(self):
        from src.api.v1.presence import presence_heartbeat, PresenceUpdate

        mock_user = MagicMock()
        mock_user.id = "user-1"
        mock_user.email = "test@example.com"

        body = PresenceUpdate(
            investigation_id="inv-1",
            cursor_position={"x": 100, "y": 200},
            selected_node_id="node-1",
        )
        result = await presence_heartbeat(body=body, current_user=mock_user)
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_get_presence_after_heartbeat(self):
        from src.api.v1.presence import presence_heartbeat, get_presence, PresenceUpdate

        mock_user = MagicMock()
        mock_user.id = "user-2"
        mock_user.email = "user2@example.com"

        body = PresenceUpdate(investigation_id="inv-2")
        await presence_heartbeat(body=body, current_user=mock_user)

        result = await get_presence(investigation_id="inv-2", current_user=mock_user)
        assert result.total >= 1

    @pytest.mark.asyncio
    async def test_leave_presence(self):
        from src.api.v1.presence import leave_presence

        mock_user = MagicMock()
        mock_user.id = "user-3"
        result = await leave_presence(investigation_id="inv-3", current_user=mock_user)
        assert result["status"] == "left"
