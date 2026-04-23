"""HubAgentGraph — stateful multi-agent orchestrator for the AI Productivity Hub.

Topology (Phase 2):
    START → supervisor → news | task | knowledge | calendar | planner | searcher → END

Each node is an async agent function from agents/.
Routing is driven by `current_agent` in HubState — the same LangGraph-compatible
pattern used throughout this codebase (API-compatible with langgraph.StateGraph).

Key design decisions:
- Dependency Inversion: all external services are injected at graph construction,
  not imported directly by agents — enables clean unit testing.
- Checkpointing: every state transition is emitted to Redis pub/sub so the WebSocket
  endpoint can stream Chain-of-Thought to the UI in real time.
- Idempotency: all agent nodes must be safe to re-run (for checkpoint resume).
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from src.adapters.hub.agents.calendar_agent import calendar_agent
from src.adapters.hub.agents.planner import CalendarService, planner_agent
from src.adapters.hub.agents.searcher import DocumentRetriever, searcher_agent
from src.adapters.hub.agents.supervisor import supervisor_agent
from src.adapters.hub.agents.synergy_planner import (
    RelevanceScorer,
    TaskRepositoryProtocol,
    synergy_planner_agent,
)
from src.adapters.hub.agents.task_agent import task_agent
from src.adapters.hub.graphs.news_graph import NewsAgentGraph
from src.adapters.hub.state import HubState

log = structlog.get_logger(__name__)

_MAX_STEPS = 10
_TERMINAL_STATES = frozenset({"done", "awaiting_hitl", "error"})


class HubAgentGraph:
    """Orchestrates the Hub multi-agent pipeline for a single task.

    Usage::

        graph = HubAgentGraph(retriever=qdrant_searcher)
        final_state = await graph.run(task_id="...", user_id="...", query="...")

    Args:
        retriever:           DocumentRetriever implementation (Qdrant in production).
        calendar_service:    CalendarMCPClient (Phase 2).
        cognitive_load_model: CognitiveLoadModel for slot scoring.
        task_repository:     HubTaskRepository for task CRUD.
        event_publisher:     Callable(task_id, event_dict) for Redis pub/sub streaming.
        tavily_searcher:     TavilySearcher for news pipeline.
        llm_summarizer:      LLMSummarizer for news summary.
        llm_critic:          LLMCritic for news reflection loop.
    """

    def __init__(
        self,
        retriever: DocumentRetriever | None = None,
        calendar_service: CalendarService | None = None,
        cognitive_load_model: Any | None = None,
        task_repository: TaskRepositoryProtocol | None = None,
        event_publisher: Any | None = None,
        tavily_searcher: Any | None = None,
        llm_summarizer: Any | None = None,
        llm_critic: Any | None = None,
        relevance_scorer: RelevanceScorer | None = None,
        qdrant_upsert: Any | None = None,
        encoder: Any | None = None,
    ) -> None:
        self._retriever = retriever
        self._calendar_service = calendar_service
        self._cognitive_load_model = cognitive_load_model
        self._task_repository = task_repository
        self._event_publisher = event_publisher
        self._relevance_scorer = relevance_scorer

        # News sub-graph (Phase 2 + storage)
        self._news_graph = NewsAgentGraph(
            tavily_searcher=tavily_searcher,
            qdrant_searcher=retriever,
            llm_summarizer=llm_summarizer,
            llm_critic=llm_critic,
            event_publisher=event_publisher,
            qdrant_upsert=qdrant_upsert,
            encoder=encoder,
        )

        # Node registry
        self._nodes: dict[str, Any] = {
            "supervisor": self._run_supervisor,
            "searcher": self._run_searcher,
            "planner": self._run_planner,
            "news": self._run_news,
            "task": self._run_task,
            "knowledge": self._run_knowledge,
            "calendar": self._run_calendar,
            # Phase 3 — cross-module synergy
            "synergy_planner": self._run_synergy_planner,
        }

    # ── Public API ──────────────────────────────────────────────────────────

    async def run(
        self,
        task_id: str,
        user_id: str,
        query: str,
        module: str = "chat",
        user_preferences: dict[str, Any] | None = None,
    ) -> HubState:
        """Execute the full agent pipeline and return the final HubState.

        The graph always starts at 'supervisor' and runs until completed
        or an error/HITL-pause terminates execution.
        """
        state: HubState = {
            "task_id": task_id,
            "user_id": user_id,
            "query": query,
            "module": module,  # type: ignore[typeddict-item]
            "user_preferences": user_preferences or {},
            "messages": [],
            "retrieved_docs": [],
            "thoughts": [],
            "result": None,
            "result_metadata": {},
            "current_agent": "supervisor",
            "next_agent": None,
            "requires_human_approval": False,
            "human_approval_pending": False,
            "error": None,
            "completed": False,
            "checkpoint_id": str(uuid.uuid4()),
            "steps_taken": 0,
        }

        await self._publish(task_id, {"type": "graph_start", "task_id": task_id})
        state = await self._execute_loop(state)
        # NOTE: graph_done is published by the caller (hub_tasks.py) AFTER writing
        # results to Redis, so the frontend always fetches a non-null result.

        return state

    async def resume_after_hitl(
        self,
        state: HubState,
        approved: bool,
    ) -> HubState:
        """Resume a paused graph after Human-in-the-Loop approval/rejection.

        Args:
            state:    The HubState exactly as returned by a previous run().
            approved: True = continue; False = abort with graceful message.
        """
        task_id = state.get("task_id", "?")

        if not approved:
            state["completed"] = True
            state["result"] = (
                "Action cancelled — human approval was not granted. "
                "No changes were made."
            )
            state["current_agent"] = "done"
            state["human_approval_pending"] = False
            await self._publish(task_id, {"type": "hitl_rejected", "task_id": task_id})
            return state

        # Approved — re-enter at the appropriate agent
        state["human_approval_pending"] = False
        state["requires_human_approval"] = False
        state["hitl_already_approved"] = True

        # Determine which agent was waiting for approval
        # Default to planner for backward compatibility
        waiting_agent = state.get("result_metadata", {}).get("waiting_agent", "planner")
        state["current_agent"] = waiting_agent

        await self._publish(task_id, {"type": "hitl_approved", "task_id": task_id})
        return await self._execute_loop(state)

    # ── Private loop ────────────────────────────────────────────────────────

    async def _execute_loop(self, state: HubState) -> HubState:
        """Drive the agent graph until a terminal state is reached."""
        task_id = state.get("task_id", "?")

        while (
            not state.get("completed")
            and state.get("steps_taken", 0) < _MAX_STEPS
        ):
            current = state.get("current_agent", "done")
            if current in _TERMINAL_STATES:
                break

            node_fn = self._nodes.get(current)
            if node_fn is None:
                await log.aerror(
                    "hub_unknown_node",
                    node=current,
                    task_id=task_id,
                )
                state["error"] = f"Unknown agent node: {current!r}"
                state["completed"] = True
                break

            await log.ainfo("hub_node_start", node=current, task_id=task_id)
            await self._publish(task_id, {"type": "node_start", "node": current})

            try:
                update = await node_fn(state)
                state.update(update)  # type: ignore[arg-type]
            except Exception as exc:
                await log.aerror(
                    "hub_node_error",
                    node=current,
                    task_id=task_id,
                    error=str(exc),
                )
                state["error"] = str(exc)
                state["completed"] = True
                break

            # Stream any new thoughts to the UI
            await self._stream_thoughts(task_id, state)

            state["steps_taken"] = state.get("steps_taken", 0) + 1
            await log.ainfo(
                "hub_node_done",
                node=current,
                task_id=task_id,
                steps=state["steps_taken"],
            )

        return state

    # ── Agent wrappers ───────────────────────────────────────────────────────

    async def _run_supervisor(self, state: HubState) -> dict[str, Any]:
        return await supervisor_agent(state)

    async def _run_searcher(self, state: HubState) -> dict[str, Any]:
        return await searcher_agent(state, retriever=self._retriever)

    async def _run_planner(self, state: HubState) -> dict[str, Any]:
        return await planner_agent(state, calendar_service=self._calendar_service)

    async def _run_news(self, state: HubState) -> dict[str, Any]:
        """Run the full news pipeline via NewsAgentGraph and map result to HubState."""
        task_id = state.get("task_id", "?")
        user_id = state.get("user_id", "")
        query = state.get("query", "")
        prefs = state.get("user_preferences") or {}

        news_state = await self._news_graph.run(
            task_id=task_id,
            user_id=user_id,
            query=query,
            user_preferences=prefs,  # type: ignore[arg-type]
        )

        # Map news pipeline output back to HubState format
        final_articles = news_state.get("final_articles") or []
        action_signals = news_state.get("action_signals") or []
        thoughts = list(state.get("thoughts") or []) + list(news_state.get("thoughts") or [])

        if news_state.get("error"):
            return {
                "thoughts": thoughts,
                "error": news_state["error"],
                "completed": True,
                "current_agent": "done",
            }

        summary_lines = [f"**News Research Results** ({len(final_articles)} articles):", ""]
        for article in final_articles[:5]:
            summary_lines.append(f"- **{article.get('title', 'Untitled')}**")
            if article.get("summary"):
                summary_lines.append(f"  {article['summary'][:200]}")

        if action_signals:
            summary_lines += ["", f"**{len(action_signals)} action signal(s) detected.**"]

        result_text = "\n".join(summary_lines)

        # Phase 3: route to synergy_planner when high-relevance signals exist
        next_agent = "synergy_planner" if action_signals else "done"
        is_completed = not bool(action_signals)

        return {
            "result": result_text,
            "result_metadata": {
                "agent": "news",
                "article_count": len(final_articles),
                "action_signals": action_signals,
                "final_articles": final_articles,
            },
            "thoughts": thoughts,
            "current_agent": next_agent,
            "requires_human_approval": False,
            "human_approval_pending": False,
            "completed": is_completed,
            "error": None,
        }

    async def _run_task(self, state: HubState) -> dict[str, Any]:
        return await task_agent(state, task_repository=self._task_repository)

    async def _run_knowledge(self, state: HubState) -> dict[str, Any]:
        """Knowledge queries fall back to the searcher (searches knowledge collection)."""
        return await searcher_agent(state, retriever=self._retriever)

    async def _run_calendar(self, state: HubState) -> dict[str, Any]:
        return await calendar_agent(
            state,
            calendar_service=self._calendar_service,
            cognitive_load_model=self._cognitive_load_model,
        )

    async def _run_synergy_planner(self, state: HubState) -> dict[str, Any]:
        return await synergy_planner_agent(
            state,
            task_repository=self._task_repository,
            relevance_scorer=self._relevance_scorer,
        )

    # ── Event publishing ────────────────────────────────────────────────────

    async def _publish(self, task_id: str, event: dict[str, Any]) -> None:
        """Emit an event to the streaming channel (Redis pub/sub or no-op)."""
        if self._event_publisher is not None:
            try:
                await self._event_publisher(task_id, event)
            except Exception:
                pass  # Never let pub/sub failure abort the agent pipeline

    async def _stream_thoughts(self, task_id: str, state: HubState) -> None:
        """Publish new Chain-of-Thought entries to the streaming channel."""
        thoughts = state.get("thoughts") or []
        if thoughts:
            await self._publish(
                task_id,
                {"type": "thought", "task_id": task_id, "thought": thoughts[-1]},
            )
