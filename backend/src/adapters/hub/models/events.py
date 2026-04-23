"""Phase 3 — Cross-Module Synergy event and proposal schemas.

These Pydantic models form the contract between the SynergyAgent (news module)
and the PlannerAgent (task / calendar modules).  Every cross-module change goes
through explicit user approval before being committed — never auto-applied.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class SuggestedAction(BaseModel):
    """A single atomic action proposed by the Planner after a synergy signal."""

    action_type: Literal["update_task", "create_task", "reschedule_event"]
    target_id: str | None = Field(
        None,
        description="task_id or calendar event_id to be modified (None for create).",
    )
    field: str | None = Field(
        None,
        description="Task/event field to update (e.g. 'description', 'priority').",
    )
    proposed_value: Any = Field(
        None,
        description="New value for the field.",
    )
    reason: str = Field(..., description="Human-readable justification for the proposal.")


class TaskModificationProposal(BaseModel):
    """A proposed change to an existing task derived from a news finding."""

    proposal_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str
    task_title: str
    field: str = Field(..., description="Task field to be modified, e.g. 'description'.")
    current_value: Any = None
    proposed_value: Any
    reason: str


class CalendarAdjustmentProposal(BaseModel):
    """A proposed calendar schedule change triggered by a task priority shift."""

    proposal_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_id: str | None = None
    summary: str = Field(..., description="Human-readable description of the adjustment.")
    proposed_reschedule: str | None = Field(
        None,
        description="ISO-8601 datetime string of the proposed new slot.",
    )
    reason: str


class AgentEvent(BaseModel):
    """Structured event emitted by any Hub agent for cross-module routing.

    The Supervisor receives these events and routes them to the appropriate
    downstream agent.  All events with requires_approval=True must pass through
    a Human-in-the-Loop pause before their proposed actions are committed.
    """

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_module: Literal["news", "tasks", "calendar", "knowledge"]
    event_type: str = Field(
        ...,
        description="e.g. 'news_action_signal', 'task_priority_change'.",
    )
    payload: dict[str, Any] = Field(default_factory=dict)
    action_relevance_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence that this event warrants a cross-module action.",
    )
    suggested_actions: list[SuggestedAction] = Field(default_factory=list)
    requires_approval: bool = True
    emitted_at: datetime = Field(default_factory=datetime.utcnow)


class SynergyChain(BaseModel):
    """The full cross-module proposal chain shown to the user for approval.

    Contains the triggering news signal, the proposed task changes, and any
    calendar adjustments that follow from those task changes.
    """

    chain_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event: AgentEvent
    news_headline: str
    news_url: str | None = None
    task_proposals: list[TaskModificationProposal] = Field(default_factory=list)
    calendar_proposals: list[CalendarAdjustmentProposal] = Field(default_factory=list)
    status: Literal["pending", "approved", "dismissed"] = "pending"
    dismissed_at: datetime | None = None
