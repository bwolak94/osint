"""Planner agent — task decomposition and schedule proposals.

Responsibilities:
- Accept planning queries (schedules, tasks, goals)
- Decompose goals into actionable sub-tasks
- Propose an ordered, prioritised plan
- Flag high-risk calendar writes for Human-in-the-Loop approval

Design: calendar_service injected via kwargs (DIP).
High-risk actions set requires_human_approval=True and halt execution.
"""

from __future__ import annotations

from typing import Any, Protocol

import structlog

from src.adapters.hub.state import HubMessage, HubState

log = structlog.get_logger(__name__)

# Keywords that signal a write operation requiring HiL approval
_WRITE_KEYWORDS: frozenset[str] = frozenset(
    {
        "delete", "remove", "cancel", "book", "create meeting",
        "schedule appointment", "send", "email",
    }
)


class CalendarService(Protocol):
    """Interface for calendar read operations (writes require HiL approval)."""

    async def get_free_slots(self, duration_minutes: int) -> list[dict[str, str]]: ...


def _requires_approval(query: str) -> bool:
    """Return True if the query intends a write/destructive calendar action."""
    lowered = query.lower()
    return any(kw in lowered for kw in _WRITE_KEYWORDS)


def _decompose_goal(query: str) -> list[str]:
    """Break a high-level goal into sub-tasks.

    Phase 1: Rule-based decomposition.
    Phase 3: Replace with LLM-based Planning agent.
    """
    # Minimal decomposition for Phase 1 scaffold
    return [
        f"1. Clarify objective: '{query}'",
        "2. Identify dependencies and blockers",
        "3. Estimate effort and assign priorities",
        "4. Block time on calendar",
        "5. Set reminder checkpoints",
    ]


async def planner_agent(
    state: HubState,
    calendar_service: CalendarService | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Decompose the user's goal and produce an actionable plan.

    Args:
        state:            Shared HubState.
        calendar_service: Injected CalendarService (real or mock).
        **kwargs:         Ignored — uniform agent signature.

    Returns:
        Partial HubState update dict.
    """
    task_id = state.get("task_id", "?")
    query = state.get("query", "")

    await log.ainfo("planner_start", task_id=task_id)

    thoughts: list[str] = list(state.get("thoughts") or [])
    messages: list[HubMessage] = list(state.get("messages") or [])

    # ── Human-in-the-Loop gate ─────────────────────────────────────────────
    # Skip HiL check if the action was already approved in a previous HITL cycle
    already_approved = state.get("hitl_already_approved", False)
    if _requires_approval(query) and not already_approved:
        thoughts.append(
            "Planner: detected write/destructive intent — pausing for human approval."
        )
        await log.awarning("planner_hitl_required", task_id=task_id, query=query[:80])
        return {
            "thoughts": thoughts,
            "messages": messages,
            "requires_human_approval": True,
            "human_approval_pending": True,
            "current_agent": "awaiting_hitl",
            "completed": False,
            "error": None,
        }

    # ── Goal decomposition ─────────────────────────────────────────────────
    thoughts.append("Planner: decomposing goal into actionable sub-tasks…")
    sub_tasks = _decompose_goal(query)

    # ── Optional calendar slot fetch ───────────────────────────────────────
    free_slots: list[dict[str, str]] = []
    if calendar_service is not None:
        try:
            free_slots = await calendar_service.get_free_slots(duration_minutes=60)
            thoughts.append(f"Planner: found {len(free_slots)} free calendar slot(s).")
        except Exception as exc:
            await log.awarning("calendar_service_error", task_id=task_id, error=str(exc))
            thoughts.append("Planner: calendar unavailable — plan produced without scheduling.")

    # ── Build plan output ──────────────────────────────────────────────────
    plan_lines = ["**Proposed Plan:**", ""] + sub_tasks
    if free_slots:
        plan_lines += ["", "**Suggested time slots:**"]
        for slot in free_slots[:3]:  # show at most 3
            plan_lines.append(f"- {slot.get('start', '?')} – {slot.get('end', '?')}")

    plan_text = "\n".join(plan_lines)
    thoughts.append("Planner: plan ready for review.")

    messages.append(HubMessage(role="assistant", content=plan_text, name="planner"))

    await log.ainfo("planner_done", task_id=task_id, sub_tasks=len(sub_tasks))

    return {
        "result": plan_text,
        "result_metadata": {
            "agent": "planner",
            "sub_tasks": sub_tasks,
            "free_slots": free_slots,
        },
        "thoughts": thoughts,
        "messages": messages,
        "current_agent": "done",
        "requires_human_approval": False,
        "human_approval_pending": False,
        "completed": True,
        "error": None,
    }
