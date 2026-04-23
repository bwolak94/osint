"""Request/response schemas for the Hub API endpoints.

All schemas are Pydantic v2 models with strict validation.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ── Phase 3: Synergy schemas ──────────────────────────────────────────────────

class SynergyDismissRequest(BaseModel):
    """POST /api/v1/hub/synergy/{event_id}/dismiss — dismiss a synergy suggestion."""

    user_id: str = Field(..., description="User dismissing the suggestion.")
    reason: str = Field(default="user_dismissed")


class SynergyDismissResponse(BaseModel):
    """Response after dismissing a synergy chain."""

    event_id: str
    dismissed: bool = True
    message: str = "Suggestion dismissed and logged to episodic memory."


# ── Core request/response schemas ─────────────────────────────────────────────

class AgentRunRequest(BaseModel):
    """POST /api/v1/hub/agent/run — enqueue a new hub task."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        description="Natural language query for the hub agent.",
    )
    module: Literal["news", "calendar", "tasks", "knowledge", "chat"] = Field(
        default="chat",
        description="Target hub module context.",
    )
    user_preferences: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional user preferences override for this run.",
    )


class AgentRunResponse(BaseModel):
    """Immediate response after enqueueing a hub task."""

    task_id: str = Field(..., description="Unique task identifier for polling/streaming.")
    status: Literal["queued"] = "queued"
    stream_url: str = Field(
        ...,
        description="WebSocket URL to stream agent events in real time.",
    )


class AgentStatusResponse(BaseModel):
    """GET /api/v1/hub/tasks/{task_id} — current task status."""

    task_id: str
    status: Literal["queued", "running", "completed", "failed", "awaiting_hitl"]
    result: str | None = None
    result_metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    thoughts: list[str] = Field(default_factory=list)
    # Phase 3: cross-module synergy chains pending user approval
    synergy_chains: list[dict[str, Any]] = Field(default_factory=list)


class HitlApprovalRequest(BaseModel):
    """POST /api/v1/hub/tasks/{task_id}/approve — resolve a HITL gate."""

    approved: bool = Field(..., description="True to continue; False to abort.")


class HitlApprovalResponse(BaseModel):
    """Response after HITL gate resolution."""

    task_id: str
    approved: bool
    status: Literal["resumed", "aborted"]
