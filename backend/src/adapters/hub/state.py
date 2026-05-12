"""HubState — shared state that flows through the Hub multi-agent graph.

Follows the LangGraph-compatible TypedDict pattern used throughout this project.
Each agent function receives the full state and returns a partial update dict.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict


class UserPreferences(TypedDict, total=False):
    """User-level configuration persisted between sessions."""

    language: str           # "en" | "pl"
    news_topics: list[str]  # Topic interest profile for news agent
    schedule_style: str     # "aggressive" | "balanced" | "relaxed"


class HubMessage(TypedDict):
    """A single message in the hub conversation."""

    role: Literal["user", "assistant", "tool"]
    content: str
    name: str | None  # agent name for 'tool' role


class RetrievedDoc(TypedDict):
    """A document chunk retrieved from the Qdrant knowledge base."""

    doc_id: str
    chunk_index: int
    text: str
    source: str
    score: float
    tags: list[str]


class HubState(TypedDict, total=False):
    """Mutable shared state that flows through all Hub agent nodes.

    All fields are optional (total=False) so partial updates via dict.update()
    merge cleanly without overwriting unrelated fields.
    """

    # ── Identity ─────────────────────────────────────────────────────────────
    task_id: str
    user_id: str

    # ── Input ────────────────────────────────────────────────────────────────
    module: Literal["news", "calendar", "tasks", "knowledge", "chat"]
    query: str
    user_preferences: UserPreferences

    # ── Conversation ─────────────────────────────────────────────────────────
    messages: list[HubMessage]

    # ── Semantic memory (Qdrant retrieval results) ───────────────────────────
    retrieved_docs: list[RetrievedDoc]

    # ── Agent reasoning trace (streamed to UI via Redis pub/sub) ─────────────
    thoughts: list[str]

    # ── Agent output ─────────────────────────────────────────────────────────
    result: str | None
    result_metadata: dict[str, Any]

    # ── Orchestration bookkeeping ─────────────────────────────────────────────
    current_agent: str
    next_agent: str | None
    requires_human_approval: bool
    human_approval_pending: bool
    error: str | None
    completed: bool

    # ── Phase 3: Cross-module synergy ────────────────────────────────────────
    # Populated after news pipeline completes with high-relevance signals.
    # Each entry is a serialised SynergyChain dict awaiting user approval.
    synergy_chains: list[dict[str, Any]]

    # Tracks which agent should resume after a HITL approval (e.g. "synergy_planner")
    hitl_already_approved: bool
    hitl_waiting_agent: str | None

    # ── Checkpoint traceability ───────────────────────────────────────────────
    checkpoint_id: str | None
    steps_taken: int
