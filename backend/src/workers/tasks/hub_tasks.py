"""Celery tasks for the Hub AI Productivity module.

Tasks run on the 'light' queue (API calls, not Playwright).
Each task:
  1. Updates Redis task status throughout execution
  2. Publishes events to the Redis pub/sub channel for WebSocket streaming
  3. Persists the final result to Redis for polling clients
  4. Checkpoints HubState on HITL pause (enables resume_hub_agent_task)
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog

from src.workers.celery_app import celery_app

log = structlog.get_logger(__name__)

_TASK_STATUS_KEY = "hub:task:{}:status"
_TASK_RESULT_KEY = "hub:task:{}:result"
_TASK_STATE_KEY = "hub:task:{}:state"
_EVENTS_CHANNEL = "hub:task:{}:events"
_TTL = 3600  # 1 hour


def _get_redis_sync() -> Any:
    """Synchronous Redis client for Celery worker context."""
    from redis import Redis as SyncRedis
    from src.config import get_settings
    settings = get_settings()
    return SyncRedis.from_url(settings.redis_url, decode_responses=True)


async def _publish_event(task_id: str, event: dict[str, Any]) -> None:
    """Publish a single event to the Redis pub/sub channel for a task."""
    import redis.asyncio as aioredis
    from src.config import get_settings
    r = aioredis.from_url(get_settings().redis_url)
    channel = _EVENTS_CHANNEL.format(task_id)
    await r.publish(channel, json.dumps(event))
    await r.aclose()


def _build_graph(task_id: str) -> Any:
    """Construct a HubAgentGraph with production dependencies."""
    from src.adapters.hub.graph import HubAgentGraph
    from src.adapters.langsmith.tracing import get_tracer

    async def _publish(tid: str, event: dict[str, Any]) -> None:
        await _publish_event(tid, event)

    # Wire Qdrant retriever
    retriever = None
    try:
        from src.adapters.qdrant.search import QdrantHybridSearcher
        from src.adapters.qdrant.client import get_qdrant_client
        retriever = QdrantHybridSearcher(client=get_qdrant_client())
    except Exception:
        pass

    # Wire Tavily searcher
    tavily_searcher = None
    try:
        from src.config import get_settings
        settings = get_settings()
        if getattr(settings, "tavily_api_key", None):
            from src.adapters.hub.adapters.tavily import TavilySearcherImpl
            tavily_searcher = TavilySearcherImpl(api_key=settings.tavily_api_key)
    except Exception:
        pass

    # Wire cognitive load model
    cognitive_load_model = None
    try:
        from src.adapters.hub.cognitive_model import get_cognitive_model
        import redis as sync_redis
        from src.config import get_settings
        settings = get_settings()
        r = sync_redis.from_url(settings.redis_url)
        cognitive_load_model = get_cognitive_model(user_id="system", redis_client=r)
    except Exception:
        pass

    # Wire Google Calendar MCP client (HTTP/SSE — STDIO banned, April 2026 RCE)
    calendar_service = None
    try:
        from src.config import get_settings
        from src.adapters.mcp.google_calendar import GoogleCalendarMCPClient
        settings = get_settings()
        if getattr(settings, "google_calendar_oauth_token", ""):
            calendar_service = GoogleCalendarMCPClient(
                server_url=settings.google_calendar_mcp_url,
                token=settings.google_calendar_oauth_token,
            )
    except Exception:
        pass

    # Wire LLM summarizer and critic
    llm_summarizer = None
    llm_critic = None
    try:
        from src.config import get_settings
        from src.adapters.hub.adapters.llm import LLMCriticImpl, LLMSummarizerImpl
        settings = get_settings()
        provider = getattr(settings, "llm_provider", "openai")
        if provider == "anthropic" and getattr(settings, "anthropic_api_key", ""):
            llm_summarizer = LLMSummarizerImpl(
                api_key=settings.anthropic_api_key,
                provider="anthropic",
                model=getattr(settings, "anthropic_model", "claude-haiku-4-5-20251001"),
            )
            llm_critic = LLMCriticImpl(
                api_key=settings.anthropic_api_key,
                provider="anthropic",
                model=getattr(settings, "anthropic_model", "claude-haiku-4-5-20251001"),
            )
        elif getattr(settings, "openai_api_key", ""):
            llm_summarizer = LLMSummarizerImpl(
                api_key=settings.openai_api_key,
                provider="openai",
                model=getattr(settings, "openai_model", "gpt-4o-mini"),
            )
            llm_critic = LLMCriticImpl(
                api_key=settings.openai_api_key,
                provider="openai",
                model=getattr(settings, "openai_model", "gpt-4o-mini"),
            )
    except Exception:
        pass

    # Wire HubTaskRepository (async session factory via SQLAlchemy)
    task_repository = None
    try:
        from src.adapters.repositories.hub_task_repository import HubTaskRepository
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker
        from src.config import get_settings
        settings = get_settings()
        engine = create_async_engine(settings.postgres_dsn, pool_pre_ping=True)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        # Create a single session for the lifetime of the task; closed on task end
        _task_session = async_session()
        task_repository = HubTaskRepository(session=_task_session)
    except Exception:
        pass

    return HubAgentGraph(
        retriever=retriever,
        calendar_service=calendar_service,
        cognitive_load_model=cognitive_load_model,
        task_repository=task_repository,
        event_publisher=_publish,
        tavily_searcher=tavily_searcher,
        llm_summarizer=llm_summarizer,
        llm_critic=llm_critic,
    )


@celery_app.task(
    name="hub.run_agent",
    queue="light",
    bind=True,
    max_retries=2,
    default_retry_delay=5,
)
def run_hub_agent_task(
    self: Any,
    *,
    task_id: str,
    user_id: str,
    query: str,
    module: str = "chat",
    user_preferences: dict[str, Any] | None = None,
) -> None:
    """Celery task: execute the hub agent pipeline for a new query.

    Lifecycle:
      queued → running → completed | failed | awaiting_hitl
    """
    redis = _get_redis_sync()

    try:
        redis.setex(_TASK_STATUS_KEY.format(task_id), _TTL, "running")

        async def _run() -> None:
            from src.adapters.hub.checkpointer import get_checkpointer  # noqa: PLC0415

            graph = _build_graph(task_id)
            state = await graph.run(
                task_id=task_id,
                user_id=user_id,
                query=query,
                module=module,
                user_preferences=user_preferences or {},
            )

            # ── Checkpoint state after graph completes ─────────────────────
            checkpointer = get_checkpointer()
            await checkpointer.save(
                task_id,
                state.get("current_agent", "done"),
                state,
            )

            # ── HITL pause ─────────────────────────────────────────────────
            if state.get("human_approval_pending"):
                redis.setex(_TASK_STATUS_KEY.format(task_id), _TTL, "awaiting_hitl")
                redis.setex(
                    _TASK_STATE_KEY.format(task_id),
                    _TTL,
                    json.dumps(state),
                )
                return

            # ── Completed or failed ────────────────────────────────────────
            final_status = "failed" if state.get("error") else "completed"
            redis.setex(_TASK_STATUS_KEY.format(task_id), _TTL, final_status)
            redis.setex(
                _TASK_RESULT_KEY.format(task_id),
                _TTL,
                json.dumps(
                    {
                        "result": state.get("result"),
                        "thoughts": state.get("thoughts", []),
                        "error": state.get("error"),
                        "synergy_chains": state.get("synergy_chains", []),
                        "result_metadata": state.get("result_metadata", {}),
                    }
                ),
            )
            # Publish graph_done AFTER Redis writes so the frontend fetch
            # always returns a non-null result (fixes race condition).
            await _publish_event(task_id, {"type": "graph_done", "task_id": task_id})

        asyncio.run(_run())

    except Exception as exc:
        log.error("hub_task_error", task_id=task_id, error=str(exc))
        redis.setex(_TASK_STATUS_KEY.format(task_id), _TTL, "failed")
        redis.setex(
            _TASK_RESULT_KEY.format(task_id),
            _TTL,
            json.dumps({"result": None, "thoughts": [], "error": str(exc)}),
        )
        raise self.retry(exc=exc)


@celery_app.task(
    name="hub.resume_agent",
    queue="light",
    bind=True,
    max_retries=1,
)
def resume_hub_agent_task(
    self: Any,
    *,
    task_id: str,
    state: dict[str, Any],
    approved: bool,
) -> None:
    """Celery task: resume a paused hub agent graph after HITL resolution."""
    redis = _get_redis_sync()

    try:
        redis.setex(_TASK_STATUS_KEY.format(task_id), _TTL, "running")

        async def _resume() -> None:
            from src.adapters.hub.graph import HubAgentGraph
            from src.adapters.hub.state import HubState

            graph = _build_graph(task_id)
            final_state = await graph.resume_after_hitl(
                state=state,  # type: ignore[arg-type]
                approved=approved,
            )

            final_status = "failed" if final_state.get("error") else "completed"
            redis.setex(_TASK_STATUS_KEY.format(task_id), _TTL, final_status)
            redis.setex(
                _TASK_RESULT_KEY.format(task_id),
                _TTL,
                json.dumps(
                    {
                        "result": final_state.get("result"),
                        "thoughts": final_state.get("thoughts", []),
                        "error": final_state.get("error"),
                        "synergy_chains": final_state.get("synergy_chains", []),
                    }
                ),
            )

        asyncio.run(_resume())

    except Exception as exc:
        log.error("hub_resume_error", task_id=task_id, error=str(exc))
        redis.setex(_TASK_STATUS_KEY.format(task_id), _TTL, "failed")
        raise self.retry(exc=exc)
