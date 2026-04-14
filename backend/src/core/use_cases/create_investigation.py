"""Use case: create a new investigation."""

from dataclasses import dataclass
from typing import Any, Callable, Coroutine
from uuid import UUID

from src.core.domain.entities.investigation import Investigation
from src.core.domain.events.base import DomainEvent
from src.core.domain.events.investigation import InvestigationCreated
from src.core.ports.repositories import IInvestigationRepository

# Type alias for an async event publisher
EventPublisher = Callable[[DomainEvent], Coroutine[Any, Any, None]]


@dataclass
class CreateInvestigationInput:
    """Input DTO for creating an investigation."""

    title: str
    description: str
    owner_id: UUID


class CreateInvestigation:
    """Creates a new investigation and publishes a domain event."""

    def __init__(self, repo: IInvestigationRepository, publish: EventPublisher) -> None:
        self._repo = repo
        self._publish = publish

    async def execute(self, data: CreateInvestigationInput) -> Investigation:
        """Create the investigation, persist it, and emit an event."""
        investigation = Investigation(
            title=data.title,
            description=data.description,
            owner_id=data.owner_id,
        )

        investigation = await self._repo.create(investigation)

        event = InvestigationCreated(
            investigation_id=investigation.id,
            owner_id=investigation.owner_id,
            title=investigation.title,
        )
        await self._publish(event)

        return investigation
