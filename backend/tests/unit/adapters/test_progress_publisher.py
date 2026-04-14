"""Tests for the Redis progress publisher."""

import json
import pytest
from unittest.mock import AsyncMock
from uuid import uuid4

from src.adapters.cache.progress_publisher import ProgressPublisher


class TestProgressPublisher:
    @pytest.fixture
    def redis(self):
        return AsyncMock()

    @pytest.fixture
    def publisher(self, redis):
        return ProgressPublisher(redis)

    @pytest.mark.asyncio
    async def test_publish_progress(self, publisher, redis):
        inv_id = uuid4()
        await publisher.publish_progress(inv_id, completed=5, total=10, current_scanner="holehe")

        redis.publish.assert_awaited_once()
        channel, payload = redis.publish.await_args[0]
        assert channel == f"investigation:{inv_id}:progress"
        data = json.loads(payload)
        assert data["type"] == "progress"
        assert data["completed"] == 5
        assert data["total"] == 10
        assert data["percentage"] == 50.0
        assert data["current_scanner"] == "holehe"

    @pytest.mark.asyncio
    async def test_publish_node_discovered(self, publisher, redis):
        inv_id = uuid4()
        await publisher.publish_node_discovered(inv_id, "n1", "person", "John Doe")

        redis.publish.assert_awaited_once()
        data = json.loads(redis.publish.await_args[0][1])
        assert data["type"] == "node_discovered"
        assert data["node"]["label"] == "John Doe"

    @pytest.mark.asyncio
    async def test_publish_scan_complete(self, publisher, redis):
        inv_id = uuid4()
        await publisher.publish_scan_complete(inv_id, "holehe", 15)

        data = json.loads(redis.publish.await_args[0][1])
        assert data["type"] == "scan_complete"
        assert data["scanner"] == "holehe"
        assert data["findings_count"] == 15

    @pytest.mark.asyncio
    async def test_publish_investigation_complete(self, publisher, redis):
        inv_id = uuid4()
        await publisher.publish_investigation_complete(inv_id, {"total_nodes": 42})

        data = json.loads(redis.publish.await_args[0][1])
        assert data["type"] == "investigation_complete"

    @pytest.mark.asyncio
    async def test_publish_error(self, publisher, redis):
        inv_id = uuid4()
        await publisher.publish_error(inv_id, "maigret", "Timeout after 120s")

        data = json.loads(redis.publish.await_args[0][1])
        assert data["type"] == "error"
        assert data["scanner"] == "maigret"

    @pytest.mark.asyncio
    async def test_publish_failure_does_not_raise(self, publisher, redis):
        """Publisher should swallow Redis errors gracefully."""
        redis.publish.side_effect = ConnectionError("Redis down")
        inv_id = uuid4()
        # Should not raise
        await publisher.publish_progress(inv_id, 1, 1)

    @pytest.mark.asyncio
    async def test_all_messages_have_timestamp(self, publisher, redis):
        inv_id = uuid4()
        await publisher.publish_progress(inv_id, 1, 2)
        data = json.loads(redis.publish.await_args[0][1])
        assert "timestamp" in data
