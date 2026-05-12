"""Hub domain models — AgentEvent and cross-module proposal schemas."""

from .events import (
    AgentEvent,
    CalendarAdjustmentProposal,
    SuggestedAction,
    SynergyChain,
    TaskModificationProposal,
)

__all__ = [
    "AgentEvent",
    "CalendarAdjustmentProposal",
    "SuggestedAction",
    "SynergyChain",
    "TaskModificationProposal",
]
