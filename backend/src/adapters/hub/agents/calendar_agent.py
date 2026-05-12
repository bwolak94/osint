"""Calendar agent — schedule proposal and overload detection.

Extends the planner_agent with cognitive-load-aware slot selection.

Key rules:
- All write operations (event creation) ALWAYS require HiL approval.
- The agent proposes exactly ONE optimal slot (highest cognitive load score).
- If scheduled event density exceeds the overload threshold, raises a warning.

Design: CalendarMCPClient and CognitiveLoadModel are injected (DIP).
"""

from __future__ import annotations

from typing import Any

import structlog

from src.adapters.hub.state import HubMessage, HubState

log = structlog.get_logger(__name__)

# Fraction of hours in a day that, when occupied, signals overload
_OVERLOAD_DENSITY_THRESHOLD = 0.6

# Keywords that signal a calendar write operation
_WRITE_KEYWORDS: frozenset[str] = frozenset(
    {
        "create", "book", "schedule", "add event", "new meeting",
        "new appointment", "set up", "arrange meeting",
    }
)

# Keywords that signal a read / planning query
_READ_KEYWORDS: frozenset[str] = frozenset(
    {
        "show", "list", "free", "available", "when", "slots",
        "open time", "gaps", "suggest",
    }
)


def _is_write_intent(query: str) -> bool:
    """Return True if the query requests a calendar write operation."""
    lowered = query.lower()
    return any(kw in lowered for kw in _WRITE_KEYWORDS)


def _parse_duration(query: str) -> int:
    """Extract meeting duration in minutes from query text; defaults to 60."""
    import re  # noqa: PLC0415

    match = re.search(r"(\d+)\s*(hour|hr|h)\b", query, re.IGNORECASE)
    if match:
        return int(match.group(1)) * 60

    match = re.search(r"(\d+)\s*(min|minute)\b", query, re.IGNORECASE)
    if match:
        return int(match.group(1))

    return 60  # default duration


async def calendar_agent(
    state: HubState,
    calendar_service: Any | None = None,   # CalendarMCPClient
    cognitive_load_model: Any | None = None,  # CognitiveLoadModel
    **kwargs: Any,
) -> dict[str, Any]:
    """Propose an optimal calendar slot and detect schedule overload.

    Args:
        state:               Shared HubState.
        calendar_service:    Injected CalendarMCPClient (None → mock slots).
        cognitive_load_model: Injected CognitiveLoadModel (None → no scoring).
        **kwargs:            Ignored — uniform agent signature.

    Returns:
        Partial HubState update dict.
    """
    task_id = state.get("task_id", "?")
    query = state.get("query", "")

    await log.ainfo("calendar_agent_start", task_id=task_id)

    thoughts: list[str] = list(state.get("thoughts") or [])
    messages: list[HubMessage] = list(state.get("messages") or [])

    # ── HiL gate for all write operations ─────────────────────────────────
    already_approved = state.get("hitl_already_approved", False)
    if _is_write_intent(query) and not already_approved:
        thoughts.append("CalendarAgent: write intent detected — requesting human approval.")
        await log.awarning("calendar_agent_hitl_required", task_id=task_id)
        return {
            "thoughts": thoughts,
            "messages": messages,
            "requires_human_approval": True,
            "human_approval_pending": True,
            "current_agent": "awaiting_hitl",
            "completed": False,
            "error": None,
        }

    duration_minutes = _parse_duration(query)
    thoughts.append(f"CalendarAgent: looking for {duration_minutes}-minute slots…")

    # ── Fetch existing events (for overload detection) ─────────────────────
    existing_events: list[dict[str, Any]] = []
    if calendar_service is not None:
        try:
            existing_events = await calendar_service.list_events(date_range_days=7)
        except Exception as exc:
            await log.awarning("calendar_list_error", task_id=task_id, error=str(exc))
            thoughts.append(f"CalendarAgent: could not list existing events — {exc}")

    # Overload detection: if more than threshold fraction of hours are occupied
    total_occupied_hours = len(existing_events)  # simplified: 1 event ≈ 1 hour
    working_hours_per_week = 7 * 10  # 7 days × 10 working hours
    if working_hours_per_week > 0:
        density = total_occupied_hours / working_hours_per_week
        if density > _OVERLOAD_DENSITY_THRESHOLD:
            thoughts.append(
                f"CalendarAgent: schedule density {density:.1%} exceeds overload threshold "
                f"({_OVERLOAD_DENSITY_THRESHOLD:.0%}) — consider deferring non-critical tasks."
            )
            await log.awarning(
                "calendar_overload_detected",
                task_id=task_id,
                density=density,
            )

    # ── Find best slots via cognitive load model ───────────────────────────
    best_slots: list[dict[str, Any]] = []

    if cognitive_load_model is not None:
        try:
            ranked_slots = await cognitive_load_model.find_best_slots(
                duration_minutes=duration_minutes,
                n=3,
            )
            best_slots = [dict(s) for s in ranked_slots]
            thoughts.append(
                f"CalendarAgent: cognitive model scored {len(best_slots)} candidate slots."
            )
        except Exception as exc:
            await log.awarning("cognitive_model_error", task_id=task_id, error=str(exc))
            thoughts.append(f"CalendarAgent: cognitive model unavailable — {exc}")
    elif calendar_service is not None:
        try:
            raw_slots = await calendar_service.get_free_slots(
                duration_minutes=duration_minutes
            )
            best_slots = raw_slots[:3]
        except Exception as exc:
            await log.awarning("calendar_slots_error", task_id=task_id, error=str(exc))

    # ── Build single optimal proposal ─────────────────────────────────────
    optimal_slot = best_slots[0] if best_slots else None
    thoughts.append("CalendarAgent: selecting optimal slot…")

    if optimal_slot:
        plan_lines = [
            "**Optimal Schedule Proposal:**",
            "",
            f"- **Start:** {optimal_slot.get('start', 'TBD')}",
            f"- **End:** {optimal_slot.get('end', 'TBD')}",
        ]
        if optimal_slot.get("score") is not None:
            plan_lines.append(
                f"- **Cognitive load score:** {optimal_slot['score']:.2f} / 1.00"
            )
        if len(best_slots) > 1:
            plan_lines.append("")
            plan_lines.append("*Alternative slots:*")
            for alt in best_slots[1:]:
                plan_lines.append(
                    f"  - {alt.get('start', '?')} (score: {alt.get('score', '?')})"
                )
        result_text = "\n".join(plan_lines)
    else:
        result_text = "CalendarAgent: no free slots found in the next 7 days."

    thoughts.append("CalendarAgent: proposal ready.")
    messages.append(HubMessage(role="assistant", content=result_text, name="calendar_agent"))

    await log.ainfo("calendar_agent_done", task_id=task_id, optimal_slot=optimal_slot)

    return {
        "result": result_text,
        "result_metadata": {
            "agent": "calendar_agent",
            "optimal_slot": optimal_slot,
            "all_slots": best_slots,
            "existing_event_count": len(existing_events),
        },
        "thoughts": thoughts,
        "messages": messages,
        "current_agent": "done",
        "requires_human_approval": False,
        "human_approval_pending": False,
        "completed": True,
        "error": None,
    }
