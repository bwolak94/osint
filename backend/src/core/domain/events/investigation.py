from dataclasses import dataclass
from uuid import UUID

from src.core.domain.events.base import DomainEvent


@dataclass(frozen=True)
class InvestigationCreated(DomainEvent):
    """Raised when a new investigation is created."""
    investigation_id: UUID = None  # type: ignore[assignment]
    owner_id: UUID = None  # type: ignore[assignment]
    seed_inputs: tuple = ()


@dataclass(frozen=True)
class InvestigationStatusChanged(DomainEvent):
    """Raised when an investigation transitions to a new status."""
    investigation_id: UUID = None  # type: ignore[assignment]
    old_status: str = ""
    new_status: str = ""
