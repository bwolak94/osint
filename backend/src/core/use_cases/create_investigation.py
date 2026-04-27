"""Use case: create a new investigation."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine
from uuid import UUID, uuid4

from src.core.domain.entities.investigation import Investigation
from src.core.domain.entities.types import InvestigationStatus, SeedInput
from src.core.domain.events.base import DomainEvent
from src.core.domain.events.investigation import InvestigationCreated
from src.core.ports.repositories import IInvestigationRepository

EventPublisher = Callable[[DomainEvent], Coroutine[Any, Any, None]]


@dataclass
class CreateInvestigationInput:
    title: str
    description: str | None
    owner_id: UUID
    seed_inputs: list[SeedInput] | None = None
    tags: frozenset[str] | None = None


class CreateInvestigation:
    """Creates a new investigation and publishes a domain event."""

    def __init__(self, repo: IInvestigationRepository, publish: EventPublisher) -> None:
        self._repo = repo
        self._publish = publish

    async def execute(self, data: CreateInvestigationInput) -> Investigation:
        now = datetime.now(timezone.utc)
        investigation = Investigation(
            id=uuid4(),
            owner_id=data.owner_id,
            title=data.title,
            description=data.description,
            status=InvestigationStatus.DRAFT,
            seed_inputs=data.seed_inputs or [],
            tags=data.tags or frozenset(),
            created_at=now,
            updated_at=now,
        )

        investigation = await self._repo.save(investigation)

        event = InvestigationCreated(
            investigation_id=investigation.id,
            owner_id=investigation.owner_id,
            seed_inputs=tuple(),
        )
        await self._publish(event)

        return investigation
