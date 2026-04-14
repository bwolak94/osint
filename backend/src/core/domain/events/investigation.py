"""Investigation-related domain events."""

from dataclasses import dataclass, field
from uuid import UUID

from src.core.domain.entities.investigation import InvestigationStatus
from src.core.domain.events.base import DomainEvent


@dataclass(frozen=True)
class InvestigationCreated(DomainEvent):
    """Emitted when a new investigation is created."""

    investigation_id: UUID = field(default_factory=lambda: UUID(int=0))
    owner_id: UUID = field(default_factory=lambda: UUID(int=0))
    title: str = ""
    event_type: str = "InvestigationCreated"


@dataclass(frozen=True)
class InvestigationStatusChanged(DomainEvent):
    """Emitted when an investigation changes status."""

    investigation_id: UUID = field(default_factory=lambda: UUID(int=0))
    old_status: InvestigationStatus = InvestigationStatus.DRAFT
    new_status: InvestigationStatus = InvestigationStatus.DRAFT
    event_type: str = "InvestigationStatusChanged"
