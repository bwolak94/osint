"""NewsAgentGraph — sequential multi-agent pipeline for news research.

Pipeline topology (Phase 2):
  searcher → validator → enricher → summary → critic → synergy → END

Each step is an agent function from agents/news/.  Errors are caught per-step
and stored in NewsState.error — the pipeline halts on error.

Design mirrors HubAgentGraph: dependency injection, error isolation,
thought streaming via event_publisher.
"""

from __future__ import annotations

from typing import Any

import structlog

from src.adapters.hub.agents.news.critic import LLMCritic, news_critic_agent
from src.adapters.hub.agents.news.enricher import news_enricher_agent
from src.adapters.hub.agents.news.searcher import TavilySearcher, news_searcher_agent
from src.adapters.hub.agents.news.state import NewsState
from src.adapters.hub.agents.news.storage import EncoderFn, QdrantUpsertFn, news_storage_agent
from src.adapters.hub.agents.news.summary import LLMSummarizer, news_summary_agent
from src.adapters.hub.agents.news.synergy import news_synergy_agent
from src.adapters.hub.agents.news.validator import news_validator_agent

log = structlog.get_logger(__name__)


class NewsAgentGraph:
    """Orchestrates the sequential news research pipeline.

    Usage::

        graph = NewsAgentGraph(tavily_searcher=searcher)
        final_state = await graph.run(task_id="...", user_id="...", query="AI news")

    Args:
        tavily_searcher:  TavilySearcher implementation (None → mock articles).
        qdrant_searcher:  DocumentRetriever for semantic dedup (None → skip dedup).
        llm_summarizer:   LLMSummarizer (None → extractive fallback).
        llm_critic:       LLMCritic (None → mock score 0.85).
        event_publisher:  Async callable(event_name, payload) for signal emission.
    """

    def __init__(
        self,
        tavily_searcher: TavilySearcher | None = None,
        qdrant_searcher: Any | None = None,
        llm_summarizer: LLMSummarizer | None = None,
        llm_critic: LLMCritic | None = None,
        event_publisher: Any | None = None,
        qdrant_upsert: QdrantUpsertFn | None = None,
        encoder: EncoderFn | None = None,
    ) -> None:
        self._tavily = tavily_searcher
        self._qdrant = qdrant_searcher
        self._summarizer = llm_summarizer
        self._critic = llm_critic
        self._publisher = event_publisher
        self._qdrant_upsert = qdrant_upsert
        self._encoder = encoder

    async def run(
        self,
        task_id: str,
        user_id: str,
        query: str,
        user_preferences: dict[str, Any] | None = None,
    ) -> NewsState:
        """Execute the full news pipeline and return the final NewsState."""
        state: NewsState = {
            "task_id": task_id,
            "user_id": user_id,
            "search_query": query,
            "user_preferences": user_preferences or {},
            "raw_results": [],
            "articles": [],
            "validated_articles": [],
            "enriched_articles": [],
            "summaries": [],
            "final_articles": [],
            "action_signals": [],
            "thoughts": [],
            "current_step": "start",
            "error": None,
            "completed": False,
        }

        pipeline = [
            ("searcher", self._run_searcher),
            ("validator", self._run_validator),
            ("enricher", self._run_enricher),
            ("summary", self._run_summary),
            ("critic", self._run_critic),
            ("storage", self._run_storage),   # Phase 2: persist to Qdrant
            ("synergy", self._run_synergy),
        ]

        for step_name, step_fn in pipeline:
            await log.ainfo("news_graph_step_start", step=step_name, task_id=task_id)
            try:
                update = await step_fn(state)
                state.update(update)  # type: ignore[typeddict-item]
            except Exception as exc:
                await log.aerror("news_graph_step_error", step=step_name, error=str(exc))
                state["error"] = f"{step_name}: {exc}"
                state["completed"] = False
                return state

            if state.get("error"):
                await log.awarning("news_graph_halted", step=step_name, error=state["error"])
                return state

            await self._stream_thoughts(task_id, state)

        return state

    # ── Private step wrappers ────────────────────────────────────────────────

    async def _run_searcher(self, state: NewsState) -> dict[str, Any]:
        return await news_searcher_agent(state, tavily_searcher=self._tavily)

    async def _run_validator(self, state: NewsState) -> dict[str, Any]:
        return await news_validator_agent(state, qdrant_searcher=self._qdrant)

    async def _run_enricher(self, state: NewsState) -> dict[str, Any]:
        return await news_enricher_agent(state, qdrant_searcher=self._qdrant)

    async def _run_summary(self, state: NewsState) -> dict[str, Any]:
        return await news_summary_agent(state, llm_summarizer=self._summarizer)

    async def _run_critic(self, state: NewsState) -> dict[str, Any]:
        return await news_critic_agent(
            state,
            llm_critic=self._critic,
            llm_summarizer=self._summarizer,
        )

    async def _run_storage(self, state: NewsState) -> dict[str, Any]:
        return await news_storage_agent(
            state,
            qdrant_upsert=self._qdrant_upsert,
            encoder=self._encoder,
        )

    async def _run_synergy(self, state: NewsState) -> dict[str, Any]:
        return await news_synergy_agent(state, event_publisher=self._publisher)

    # ── Event publishing ─────────────────────────────────────────────────────

    async def _stream_thoughts(self, task_id: str, state: NewsState) -> None:
        """Publish latest thought to the streaming channel."""
        if self._publisher is None:
            return
        thoughts = state.get("thoughts") or []
        if thoughts:
            try:
                await self._publisher(
                    "news_thought",
                    {"type": "thought", "task_id": task_id, "thought": thoughts[-1]},
                )
            except Exception:
                pass  # pub/sub errors must not abort the pipeline
