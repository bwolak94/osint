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
from src.adapters.hub.redis_keys import (
    HUB_TTL,
    task_status_key,
    task_result_key,
    task_state_key,
    task_events_channel,
)

log = structlog.get_logger(__name__)

# Module-level engine singleton — avoids creating a new connection pool on every task
_db_engine = None


def _get_db_engine() -> Any:
    """Return (or lazily initialise) the module-level async SQLAlchemy engine."""
    global _db_engine  # noqa: PLW0603
    if _db_engine is None:
        from sqlalchemy.ext.asyncio import create_async_engine
        from src.config import get_settings
        _db_engine = create_async_engine(get_settings().postgres_dsn, pool_pre_ping=True)
    return _db_engine


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
    channel = task_events_channel(task_id)
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
    # Fix 13: use module-level engine singleton instead of creating a new engine per task
    task_repository = None
    try:
        from src.adapters.repositories.hub_task_repository import HubTaskRepository
        from sqlalchemy.ext.asyncio import AsyncSession
        from sqlalchemy.orm import sessionmaker
        engine = _get_db_engine()
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


async def _save_conversation(
    task_id: str,
    user_id: str,
    module: str,
    query: str,
    state: dict[str, Any],
) -> None:
    """Persist the completed conversation to the hub_conversations table."""
    try:
        from sqlalchemy.ext.asyncio import AsyncSession
        from src.adapters.db.models.hub_conversation import HubConversation
        from datetime import datetime, timezone

        async with AsyncSession(_get_db_engine()) as session:
            conv = HubConversation(
                user_id=user_id,
                task_id=task_id,
                module=module,
                query=query,
                result=state.get("result"),
                error=state.get("error"),
                thoughts=state.get("thoughts", []),
                result_metadata=state.get("result_metadata", {}),
                completed_at=datetime.now(timezone.utc),
            )
            session.add(conv)
            await session.commit()
    except Exception as exc:
        log.warning("hub_conversation_save_error", task_id=task_id, error=str(exc))


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
        redis.setex(task_status_key(task_id), HUB_TTL, "running")

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
                redis.setex(task_status_key(task_id), HUB_TTL, "awaiting_hitl")
                redis.setex(
                    task_state_key(task_id),
                    HUB_TTL,
                    json.dumps(state),
                )
                return

            # ── Completed or failed ────────────────────────────────────────
            final_status = "failed" if state.get("error") else "completed"
            redis.setex(task_status_key(task_id), HUB_TTL, final_status)
            redis.setex(
                task_result_key(task_id),
                HUB_TTL,
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

            # Persist conversation to DB (non-fatal)
            await _save_conversation(task_id, user_id, module, query, state)

            # Publish graph_done AFTER Redis writes so the frontend fetch
            # always returns a non-null result (fixes race condition).
            await _publish_event(task_id, {"type": "graph_done", "task_id": task_id})

        asyncio.run(_run())

    except Exception as exc:
        log.error("hub_task_error", task_id=task_id, error=str(exc))
        redis.setex(task_status_key(task_id), HUB_TTL, "failed")
        redis.setex(
            task_result_key(task_id),
            HUB_TTL,
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
        redis.setex(task_status_key(task_id), HUB_TTL, "running")

        async def _resume() -> None:
            from src.adapters.hub.graph import HubAgentGraph
            from src.adapters.hub.state import HubState

            graph = _build_graph(task_id)
            final_state = await graph.resume_after_hitl(
                state=state,  # type: ignore[arg-type]
                approved=approved,
            )

            final_status = "failed" if final_state.get("error") else "completed"
            redis.setex(task_status_key(task_id), HUB_TTL, final_status)
            redis.setex(
                task_result_key(task_id),
                HUB_TTL,
                json.dumps(
                    {
                        "result": final_state.get("result"),
                        "thoughts": final_state.get("thoughts", []),
                        "error": final_state.get("error"),
                        "synergy_chains": final_state.get("synergy_chains", []),
                    }
                ),
            )

            # Fix 15: publish graph_done so WebSocket clients are notified after resume
            await _publish_event(task_id, {"type": "graph_done", "task_id": task_id})

        asyncio.run(_resume())

    except Exception as exc:
        log.error("hub_resume_error", task_id=task_id, error=str(exc))
        redis.setex(task_status_key(task_id), HUB_TTL, "failed")
        raise self.retry(exc=exc)
