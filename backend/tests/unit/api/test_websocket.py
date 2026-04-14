"""Tests for the WebSocket connection manager."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.api.v1.investigations.websocket import ConnectionManager


class TestConnectionManager:
    @pytest.fixture
    def manager(self):
        return ConnectionManager()

    @pytest.mark.asyncio
    async def test_connect_adds_to_pool(self, manager):
        ws = AsyncMock()
        await manager.connect("inv-1", ws)
        assert manager.active_connections == 1
        ws.accept.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disconnect_removes_from_pool(self, manager):
        ws = AsyncMock()
        await manager.connect("inv-1", ws)
        await manager.disconnect("inv-1", ws)
        assert manager.active_connections == 0

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all_connections(self, manager):
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await manager.connect("inv-1", ws1)
        await manager.connect("inv-1", ws2)

        message = {"type": "progress", "completed": 5, "total": 10}
        await manager.broadcast("inv-1", message)

        ws1.send_json.assert_awaited_once_with(message)
        ws2.send_json.assert_awaited_once_with(message)

    @pytest.mark.asyncio
    async def test_broadcast_to_different_investigations(self, manager):
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await manager.connect("inv-1", ws1)
        await manager.connect("inv-2", ws2)

        await manager.broadcast("inv-1", {"type": "progress"})

        ws1.send_json.assert_awaited_once()
        ws2.send_json.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_broadcast_removes_dead_connections(self, manager):
        ws_alive = AsyncMock()
        ws_dead = AsyncMock()
        ws_dead.send_json.side_effect = Exception("Connection closed")

        await manager.connect("inv-1", ws_alive)
        await manager.connect("inv-1", ws_dead)
        assert manager.active_connections == 2

        await manager.broadcast("inv-1", {"type": "test"})
        # Dead connection should be removed
        assert manager.active_connections == 1

    @pytest.mark.asyncio
    async def test_empty_broadcast_no_error(self, manager):
        # Broadcasting to an investigation with no connections should not raise
        await manager.broadcast("nonexistent", {"type": "test"})
