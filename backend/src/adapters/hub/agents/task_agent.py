"""Task management agent for the Hub AI Productivity module.

Responsibilities:
- Parse user query to detect list / create / update intent
- Execute the appropriate repository operation
- Return a structured result in HubState format
- Deletions ALWAYS require human approval (never auto-delete)

Design: TaskRepositoryProtocol is injected (DIP) — no direct DB import.
"""

from __future__ import annotations

import re
from typing import Any, Protocol

import structlog

from src.adapters.hub.state import HubMessage, HubState

log = structlog.get_logger(__name__)

# Intent detection patterns
_LIST_PATTERNS: frozenset[str] = frozenset(
    {"list", "show", "get", "what are my", "all tasks", "my tasks", "backlog", "view"}
)
_CREATE_PATTERNS: frozenset[str] = frozenset(
    {"create", "add", "new task", "make a task", "todo:", "new todo"}
)
_UPDATE_PATTERNS: frozenset[str] = frozenset(
    {"update", "change", "modify", "mark", "set priority", "complete", "finish", "done"}
)
_DELETE_PATTERNS: frozenset[str] = frozenset(
    {"delete", "remove", "cancel", "drop", "get rid of"}
)

# Priority keywords mapped to numeric value
_PRIORITY_KEYWORDS: dict[str, int] = {
    "critical": 1,
    "urgent": 1,
    "high": 2,
    "important": 2,
    "normal": 3,
    "medium": 3,
    "low": 4,
    "nice to have": 5,
    "optional": 5,
}


class TaskRepositoryProtocol(Protocol):
    """Minimal protocol that the task agent depends on (DIP)."""

    async def list_tasks(self, user_id: str, **kwargs: Any) -> list[dict[str, Any]]: ...
    async def create_task(self, user_id: str, data: dict[str, Any]) -> dict[str, Any]: ...
    async def update_task(
        self, user_id: str, task_id: str, data: dict[str, Any]
    ) -> dict[str, Any] | None: ...


def _classify_intent(query: str) -> str:
    """Return 'list' | 'create' | 'update' | 'delete' | 'unknown'."""
    lowered = query.lower()

    if any(kw in lowered for kw in _DELETE_PATTERNS):
        return "delete"
    if any(kw in lowered for kw in _CREATE_PATTERNS):
        return "create"
    if any(kw in lowered for kw in _UPDATE_PATTERNS):
        return "update"
    if any(kw in lowered for kw in _LIST_PATTERNS):
        return "list"
    return "list"  # default to listing for ambiguous task queries


def _extract_priority(query: str) -> int:
    """Extract priority level (1-5) from query text; defaults to 3."""
    lowered = query.lower()
    for keyword, value in _PRIORITY_KEYWORDS.items():
        if keyword in lowered:
            return value
    return 3


def _extract_title(query: str) -> str:
    """Best-effort title extraction from a create query."""
    # Strip common create verbs to get the actual task title
    cleaned = re.sub(
        r"^(create|add|new task|make a task|todo:|new todo)\s*[:—]?\s*",
        "",
        query,
        flags=re.IGNORECASE,
    ).strip()
    return cleaned or query


async def task_agent(
    state: HubState,
    task_repository: TaskRepositoryProtocol | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Route a task management query to the appropriate repository operation.

    For deletions: always raises the HiL gate — no auto-delete.

    Args:
        state:           Shared HubState.
        task_repository: Injected repository (real or mock).
        **kwargs:        Ignored — uniform agent signature.

    Returns:
        Partial HubState update dict.
    """
    task_id = state.get("task_id", "?")
    user_id = state.get("user_id", "")
    query = state.get("query", "")

    await log.ainfo("task_agent_start", task_id=task_id, query_length=len(query))

    thoughts: list[str] = list(state.get("thoughts") or [])
    messages: list[HubMessage] = list(state.get("messages") or [])

    intent = _classify_intent(query)
    thoughts.append(f"TaskAgent: detected intent '{intent}' from query.")

    # ── Delete always requires HITL — never auto-delete ────────────────────
    if intent == "delete":
        thoughts.append("TaskAgent: delete intent detected — requesting human approval.")
        await log.awarning("task_agent_hitl_required", task_id=task_id)
        return {
            "thoughts": thoughts,
            "messages": messages,
            "requires_human_approval": True,
            "human_approval_pending": True,
            "current_agent": "awaiting_hitl",
            "completed": False,
            "error": None,
        }

    result_text: str
    result_meta: dict[str, Any] = {"agent": "task_agent", "intent": intent}

    if task_repository is None:
        # Mock path for testing without a real database
        if intent == "list":
            result_text = "TaskAgent: (mock) You have 0 tasks."
        elif intent == "create":
            result_text = "TaskAgent: (mock) Task created."
        else:
            result_text = "TaskAgent: (mock) Task updated."

        thoughts.append(f"TaskAgent: (mock mode) {intent} completed.")
        messages.append(HubMessage(role="assistant", content=result_text, name="task_agent"))
        return {
            "result": result_text,
            "result_metadata": result_meta,
            "thoughts": thoughts,
            "messages": messages,
            "current_agent": "done",
            "requires_human_approval": False,
            "human_approval_pending": False,
            "completed": True,
            "error": None,
        }

    # ── Live repository operations ─────────────────────────────────────────
    try:
        if intent == "list":
            tasks = await task_repository.list_tasks(user_id=user_id)
            count = len(tasks)
            result_text = f"TaskAgent: you have {count} task(s)."
            result_meta["task_count"] = count
            result_meta["tasks"] = tasks

        elif intent == "create":
            priority = _extract_priority(query)
            title = _extract_title(query)
            task = await task_repository.create_task(
                user_id=user_id,
                data={"title": title, "priority": priority, "source": "agent"},
            )
            result_text = f"TaskAgent: created task '{title}' (priority {priority})."
            result_meta["created_task"] = task

        else:  # update
            result_text = "TaskAgent: task update requires a task ID. Please specify the task."
            result_meta["requires_task_id"] = True

        thoughts.append(f"TaskAgent: {intent} operation completed.")

    except Exception as exc:
        await log.aerror("task_agent_error", task_id=task_id, error=str(exc))
        thoughts.append(f"TaskAgent: error during {intent} — {exc}")
        return {
            "thoughts": thoughts,
            "messages": messages,
            "current_agent": "done",
            "completed": True,
            "error": str(exc),
        }

    messages.append(HubMessage(role="assistant", content=result_text, name="task_agent"))

    return {
        "result": result_text,
        "result_metadata": result_meta,
        "thoughts": thoughts,
        "messages": messages,
        "current_agent": "done",
        "requires_human_approval": False,
        "human_approval_pending": False,
        "completed": True,
        "error": None,
    }
