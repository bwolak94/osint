from dataclasses import dataclass
from uuid import UUID

from src.core.domain.events.base import DomainEvent


@dataclass(frozen=True)
class IdentityResolved(DomainEvent):
    """Raised when an identity is resolved by merging multiple sources."""
    identity_id: UUID = None  # type: ignore[assignment]
    investigation_id: UUID = None  # type: ignore[assignment]
    merged_from: tuple[UUID, ...] = ()
    confidence_score: float = 0.0
