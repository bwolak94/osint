from typing import Protocol

from src.core.domain.events.base import DomainEvent


class IEventPublisher(Protocol):
    async def publish(self, event: DomainEvent) -> None: ...
    async def publish_many(self, events: list[DomainEvent]) -> None: ...


class NoOpEventPublisher:
    """No-op event publisher for use until a real event bus is wired up.

    A shared singleton (``noop_publisher``) is provided so routers don't
    instantiate a new object on every request.
    """

    async def publish(self, event: DomainEvent) -> None:
        pass

    async def publish_many(self, events: list[DomainEvent]) -> None:
        pass


# Shared singleton — import and use directly rather than calling _NoOpEventPublisher()
# per-request in each router.
noop_publisher = NoOpEventPublisher()
