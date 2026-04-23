"""Phase 3 — Synergy Planner Agent.

Receives action signals emitted by the News SynergyAgent, queries active tasks
for semantic relevance, and generates cross-module proposals:
  - TaskModificationProposal: update description / priority for affected tasks
  - CalendarAdjustmentProposal: reschedule linked calendar events when priority shifts

All proposals are assembled into a SynergyChain and placed in HubState.
Execution is always paused here for Human-in-the-Loop approval — proposals are
NEVER auto-committed.

Design:
  - task_repository injected (DIP) — real or mock
  - relevance scorer injected — cosine similarity or stub for testing
  - no LLM calls in v1: rule-based proposal generation (LLM upgrade in Phase 4)
"""

from __future__ import annotations

import uuid
from typing import Any, Callable, Protocol

import structlog

from src.adapters.hub.models.events import (
    AgentEvent,
    CalendarAdjustmentProposal,
    SynergyChain,
    TaskModificationProposal,
)
from src.adapters.hub.state import HubState

log = structlog.get_logger(__name__)

# Minimum relevance score for a task to be included in proposals
_TASK_RELEVANCE_THRESHOLD = 0.45

# Keywords that indicate urgency — boost relevance score
_URGENT_KEYWORDS: frozenset[str] = frozenset(
    {
        "regulation", "regulatory", "compliance", "law", "deadline", "breach",
        "vulnerability", "critical", "zero-day", "embargo", "sanction", "recall",
    }
)


class TaskRepositoryProtocol(Protocol):
    async def list_tasks(self, user_id: str, **kwargs: Any) -> list[dict[str, Any]]: ...


# Relevance scorer: (finding_text, task_text) → float in [0, 1]
RelevanceScorer = Callable[[str, str], float]


def _keyword_relevance(finding_text: str, task_text: str) -> float:
    """Simple word-overlap relevance scorer (no embedding dependency).

    Phase 4 upgrade: replace with cosine_sim(embedding_A, embedding_B).
    """
    finding_words = set(finding_text.lower().split())
    task_words = set(task_text.lower().split())
    intersection = finding_words & task_words
    if not task_words:
        return 0.0
    base = len(intersection) / len(task_words)

    # Apply urgency keyword boost (max 0.2)
    boost = 0.2 if any(kw in finding_text.lower() for kw in _URGENT_KEYWORDS) else 0.0
    return min(base + boost, 1.0)


def _build_task_proposal(
    finding: dict[str, Any],
    task: dict[str, Any],
    relevance: float,
) -> TaskModificationProposal:
    """Build a TaskModificationProposal for a task affected by the news finding."""
    tags = finding.get("tags") or []
    current_desc = task.get("description") or task.get("title", "")

    # Propose a description augmentation with the relevant news context
    proposed_desc = (
        f"{current_desc}\n\n"
        f"[Synergy — {finding.get('title', 'News finding')}] "
        f"Relevance: {relevance:.0%}. Review and update if needed."
    ).strip()

    # Suggest priority escalation for high-urgency findings
    current_priority = task.get("priority", 3)
    proposed_priority = max(1, current_priority - 1) if any(
        kw in finding.get("title", "").lower() for kw in _URGENT_KEYWORDS
    ) else current_priority

    field = "description"
    proposed_value = proposed_desc

    if proposed_priority != current_priority:
        # Priority change takes precedence as the primary proposal
        field = "priority"
        proposed_value = proposed_priority

    return TaskModificationProposal(
        task_id=str(task.get("id", uuid.uuid4())),
        task_title=task.get("title", "Untitled task"),
        field=field,
        current_value=task.get(field),
        proposed_value=proposed_value,
        reason=(
            f"News finding '{finding.get('title')}' has {relevance:.0%} relevance "
            f"to this task (score: {finding.get('action_relevance_score', 0):.2f})."
        ),
    )


def _build_calendar_proposal(
    task_proposal: TaskModificationProposal,
) -> CalendarAdjustmentProposal | None:
    """Generate a calendar adjustment proposal when a task priority is escalated."""
    if task_proposal.field != "priority":
        return None

    return CalendarAdjustmentProposal(
        summary=(
            f"Consider rescheduling work on '{task_proposal.task_title}' — "
            f"priority elevated from {task_proposal.current_value} to "
            f"{task_proposal.proposed_value}."
        ),
        reason=task_proposal.reason,
    )


async def synergy_planner_agent(
    state: HubState,
    task_repository: TaskRepositoryProtocol | None = None,
    relevance_scorer: RelevanceScorer | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build cross-module proposals from news action signals.

    Reads ``result_metadata.action_signals`` populated by the news pipeline,
    queries active tasks for relevance, and assembles SynergyChain objects.
    Always sets requires_human_approval=True — never commits changes.

    Args:
        state:             Shared HubState.
        task_repository:   Injected task repository (real or mock).
        relevance_scorer:  Callable(finding_text, task_text) → float.
        **kwargs:          Ignored — uniform agent signature.

    Returns:
        Partial HubState update with synergy_chains + HITL gate.
    """
    task_id = state.get("task_id", "?")
    user_id = state.get("user_id", "")

    await log.ainfo("synergy_planner_start", task_id=task_id)

    thoughts: list[str] = list(state.get("thoughts") or [])
    action_signals: list[dict[str, Any]] = (
        state.get("result_metadata", {}).get("action_signals") or []
    )
    scorer = relevance_scorer or _keyword_relevance

    if not action_signals:
        thoughts.append("SynergyPlanner: no action signals — skipping.")
        return {
            "thoughts": thoughts,
            "current_agent": "done",
            "completed": True,
            "error": None,
        }

    # Fetch active tasks for relevance matching
    active_tasks: list[dict[str, Any]] = []
    if task_repository is not None:
        try:
            active_tasks = await task_repository.list_tasks(user_id=user_id, status="active")
        except Exception as exc:
            await log.awarning("synergy_planner_task_fetch_error", error=str(exc))
            thoughts.append(f"SynergyPlanner: could not fetch tasks — {exc}")

    thoughts.append(
        f"SynergyPlanner: processing {len(action_signals)} signal(s) "
        f"against {len(active_tasks)} task(s)."
    )

    synergy_chains: list[dict[str, Any]] = list(state.get("synergy_chains") or [])

    for signal in action_signals:
        finding_text = f"{signal.get('title', '')} {' '.join(signal.get('tags') or [])}"

        task_proposals: list[TaskModificationProposal] = []
        calendar_proposals: list[CalendarAdjustmentProposal] = []

        for task in active_tasks:
            task_text = f"{task.get('title', '')} {task.get('description', '')}"
            relevance = scorer(finding_text, task_text)

            if relevance < _TASK_RELEVANCE_THRESHOLD:
                continue

            task_proposal = _build_task_proposal(signal, task, relevance)
            task_proposals.append(task_proposal)

            cal_proposal = _build_calendar_proposal(task_proposal)
            if cal_proposal is not None:
                calendar_proposals.append(cal_proposal)

        if not task_proposals and not active_tasks:
            # No tasks to match — still surface the signal to the user
            # so they can choose to create a task from it manually.
            pass

        agent_event = AgentEvent(
            source_module="news",
            event_type="news_action_signal",
            payload=signal,
            action_relevance_score=signal.get("action_relevance_score", 0.0),
        )

        chain = SynergyChain(
            event=agent_event,
            news_headline=signal.get("title", ""),
            news_url=signal.get("url"),
            task_proposals=task_proposals,
            calendar_proposals=calendar_proposals,
        )
        synergy_chains.append(chain.model_dump())

        thoughts.append(
            f"SynergyPlanner: chain built for '{signal.get('title', '')}' — "
            f"{len(task_proposals)} task proposal(s), "
            f"{len(calendar_proposals)} calendar proposal(s)."
        )

    await log.ainfo(
        "synergy_planner_done",
        task_id=task_id,
        chains=len(synergy_chains),
    )

    # Always pause for HITL — proposals never auto-committed
    return {
        "synergy_chains": synergy_chains,
        "thoughts": thoughts,
        "requires_human_approval": True,
        "human_approval_pending": True,
        "hitl_waiting_agent": "synergy_planner",
        "current_agent": "awaiting_hitl",
        "completed": False,
        "error": None,
    }
