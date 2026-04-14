from typing import Protocol

from src.core.domain.events.base import DomainEvent


class IEventPublisher(Protocol):
    async def publish(self, event: DomainEvent) -> None: ...
    async def publish_many(self, events: list[DomainEvent]) -> None: ...
