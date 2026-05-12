"""Redis Pub/Sub event publisher."""

from __future__ import annotations

import json

import structlog

from src.core.domain.events.base import DomainEvent

log = structlog.get_logger(__name__)


class RedisEventPublisher:
    """Publishes domain events to Redis Pub/Sub channels.

    Each event is published to a channel named after its class:
    ``events:{EventClassName}`` (e.g. ``events:InvestigationCreated``).
    """

    def __init__(self, redis: object) -> None:
        self._redis = redis

    async def publish(self, event: DomainEvent) -> None:
        channel = f"events:{type(event).__name__}"
        payload = json.dumps({
            "type": type(event).__name__,
            "data": getattr(event, "__dict__", {}),
        }, default=str)
        try:
            await self._redis.publish(channel, payload)  # type: ignore[union-attr]
        except Exception as exc:
            log.warning("Failed to publish domain event", event_type=type(event).__name__, error=str(exc))

    async def publish_many(self, events: list[DomainEvent]) -> None:
        for event in events:
            await self.publish(event)
