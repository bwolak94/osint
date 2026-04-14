"""Domain events."""

from src.core.domain.events.base import DomainEvent
from src.core.domain.events.investigation import InvestigationCreated, InvestigationStatusChanged

__all__ = [
    "DomainEvent",
    "InvestigationCreated",
    "InvestigationStatusChanged",
]
