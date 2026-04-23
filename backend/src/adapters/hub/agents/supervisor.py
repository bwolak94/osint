"""Supervisor agent — routes tasks to specialist agents.

Responsibilities:
- Classify user intent from the query
- Set `next_agent` to delegate to the appropriate specialist
- Maintain system-level view: prevents duplicate work, manages context budget
- Never calls LLM tools directly — delegates only (SRP)

Phase 2: Extended routing to news, tasks, knowledge, calendar, planner, searcher.
Phase 3: Replace keyword heuristics with LLM-based intent classification.
"""

from __future__ import annotations

import structlog

from src.adapters.hub.state import HubMessage, HubState

log = structlog.get_logger(__name__)

# ── Intent keyword sets ────────────────────────────────────────────────────────
# More specific agents listed first to win on keyword overlap.

_NEWS_KEYWORDS: frozenset[str] = frozenset(
    {
        "news", "article", "latest", "headlines", "trending", "breaking",
        "what happened", "recent events", "current events",
    }
)

_TASK_KEYWORDS: frozenset[str] = frozenset(
    {
        "task", "todo", "priority", "backlog", "to-do", "action item",
        "checklist", "my tasks", "create task", "new task", "list tasks",
    }
)

_KNOWLEDGE_KEYWORDS: frozenset[str] = frozenset(
    {
        "knowledge", "document", "pdf", "wiki", "note", "upload", "ingest",
        "knowledge base", "reference", "documentation", "manual",
    }
)

_CALENDAR_KEYWORDS: frozenset[str] = frozenset(
    {
        "calendar", "schedule", "meeting", "appointment", "slot", "book",
        "free time", "available", "when am i free", "event", "block time",
    }
)

_PLANNER_KEYWORDS: frozenset[str] = frozenset(
    {
        "plan", "organize", "prioritize", "arrange", "deadline", "remind",
        "goal", "milestones", "roadmap",
    }
)

_SEARCHER_KEYWORDS: frozenset[str] = frozenset(
    {
        "find", "search", "research", "what", "who", "when", "how",
        "explain", "summarize", "read", "learn", "show",
    }
)

# Ordered list of (agent_name, keyword_set) — first match wins on tie-break.
# More specific agents are listed before general ones.
_INTENT_MAP: list[tuple[str, frozenset[str]]] = [
    ("news", _NEWS_KEYWORDS),
    ("task", _TASK_KEYWORDS),
    ("knowledge", _KNOWLEDGE_KEYWORDS),
    ("calendar", _CALENDAR_KEYWORDS),
    ("planner", _PLANNER_KEYWORDS),
    ("searcher", _SEARCHER_KEYWORDS),
]


def _classify_intent(
    query: str,
) -> str:
    """Determine the target specialist agent from the user query.

    Uses keyword heuristics; returns the agent with the most keyword matches.
    Ties are broken by the ordering in _INTENT_MAP (most specific first).

    Returns:
        Agent name: "news" | "task" | "knowledge" | "calendar" | "planner" | "searcher"
    """
    lowered = query.lower()
    best_agent = "searcher"
    best_score = 0

    for agent_name, keywords in _INTENT_MAP:
        score = sum(1 for kw in keywords if kw in lowered)
        if score > best_score:
            best_score = score
            best_agent = agent_name

    return best_agent


async def supervisor_agent(state: HubState, **kwargs: object) -> dict[str, object]:
    """Route the user query to the appropriate specialist agent.

    Returns a partial HubState update dict — only the fields this
    agent is responsible for changing.
    """
    task_id = state.get("task_id", "?")
    query = state.get("query", "")

    await log.ainfo("supervisor_routing", task_id=task_id, query_length=len(query))

    if not query.strip():
        return {
            "error": "Empty query received by supervisor",
            "completed": True,
            "current_agent": "done",
        }

    next_agent = _classify_intent(query)
    thought = f"Supervisor: routing to '{next_agent}' agent based on query intent."

    await log.ainfo(
        "supervisor_decision",
        task_id=task_id,
        next_agent=next_agent,
        query_preview=query[:80],
    )

    # Append supervisor thought to the thought stream
    existing_thoughts: list[str] = list(state.get("thoughts") or [])
    existing_thoughts.append(thought)

    # Append supervisor assistant message
    messages: list[HubMessage] = list(state.get("messages") or [])
    messages.append(
        HubMessage(role="assistant", content=thought, name="supervisor")
    )

    return {
        "current_agent": next_agent,
        "thoughts": existing_thoughts,
        "messages": messages,
        "requires_human_approval": False,
        "human_approval_pending": False,
        "error": None,
    }
