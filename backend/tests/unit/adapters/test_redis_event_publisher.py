"""Tests for RedisEventPublisher — verifies publish/publish_many behaviour."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.adapters.events.redis_publisher import RedisEventPublisher
from src.core.domain.events.base import DomainEvent


class UserLoggedIn(DomainEvent):
    def __init__(self, user_id: str, ip_address: str | None = None) -> None:
        self.user_id = user_id
        self.ip_address = ip_address


class TestRedisEventPublisher:
    async def test_publish_calls_redis_publish(self) -> None:
        redis = MagicMock()
        redis.publish = AsyncMock()

        publisher = RedisEventPublisher(redis)
        event = UserLoggedIn(user_id="user-123", ip_address="1.2.3.4")
        await publisher.publish(event)

        redis.publish.assert_awaited_once()
        channel, payload = redis.publish.call_args.args
        assert channel == "events:UserLoggedIn"

        data = json.loads(payload)
        assert data["type"] == "UserLoggedIn"

    async def test_publish_channel_named_after_event_class(self) -> None:
        redis = MagicMock()
        redis.publish = AsyncMock()

        publisher = RedisEventPublisher(redis)

        class InvestigationStarted(DomainEvent):
            pass

        await publisher.publish(InvestigationStarted())
        channel = redis.publish.call_args.args[0]
        assert channel == "events:InvestigationStarted"

    async def test_publish_many_calls_publish_for_each_event(self) -> None:
        redis = MagicMock()
        redis.publish = AsyncMock()

        publisher = RedisEventPublisher(redis)
        events: list[DomainEvent] = [
            UserLoggedIn(user_id="u1"),
            UserLoggedIn(user_id="u2"),
            UserLoggedIn(user_id="u3"),
        ]
        await publisher.publish_many(events)
        assert redis.publish.await_count == 3

    async def test_publish_does_not_raise_on_redis_error(self) -> None:
        """Publisher must not propagate Redis connection errors — graceful degradation."""
        redis = MagicMock()
        redis.publish = AsyncMock(side_effect=ConnectionError("Redis down"))

        publisher = RedisEventPublisher(redis)
        # Should not raise
        await publisher.publish(UserLoggedIn(user_id="u1"))

    async def test_publish_many_continues_on_partial_failure(self) -> None:
        """If one event fails, subsequent events are still published."""
        call_count = 0

        async def flaky_publish(channel: str, payload: str) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise ConnectionError("transient error")

        redis = MagicMock()
        redis.publish = flaky_publish

        publisher = RedisEventPublisher(redis)
        await publisher.publish_many([
            UserLoggedIn(user_id="u1"),
            UserLoggedIn(user_id="u2"),
            UserLoggedIn(user_id="u3"),
        ])
        # All 3 attempts were made even though the 2nd raised
        assert call_count == 3
