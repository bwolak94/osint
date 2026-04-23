"""Hub API router — agent execution, status polling, WebSocket streaming, HITL.

Endpoints:
  POST  /api/v1/hub/agent/run              → enqueue task, return task_id
  GET   /api/v1/hub/tasks/{task_id}        → poll task status
  WS    /api/v1/hub/tasks/{task_id}/stream → real-time event stream
  POST  /api/v1/hub/tasks/{task_id}/approve → resolve HITL gate

Design:
- POST /agent/run is non-blocking: it enqueues a Celery task and returns immediately.
- Clients subscribe to the WebSocket to receive streamed Chain-of-Thought events.
- Redis pub/sub channel: "hub:task:{task_id}:events"
"""

from __future__ import annotations

import json
import uuid
from typing import AsyncGenerator

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from src.api.v1.hub.schemas import (
    AgentRunRequest,
    AgentRunResponse,
    AgentStatusResponse,
    HitlApprovalRequest,
    HitlApprovalResponse,
    SynergyDismissRequest,
    SynergyDismissResponse,
)
from src.workers.tasks.hub_tasks import run_hub_agent_task, resume_hub_agent_task

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/hub", tags=["hub"])

# Redis key helpers
_TASK_STATUS_KEY = "hub:task:{}:status"
_TASK_RESULT_KEY = "hub:task:{}:result"
_TASK_STATE_KEY = "hub:task:{}:state"
_EVENTS_CHANNEL = "hub:task:{}:events"


def _get_redis() -> Redis:
    """Create a Redis client from settings."""
    import redis.asyncio as aioredis
    from src.config import get_settings
    return aioredis.from_url(get_settings().redis_url, decode_responses=True)


@router.post("/agent/run", response_model=AgentRunResponse, status_code=202)
async def run_agent(body: AgentRunRequest) -> AgentRunResponse:
    """Enqueue a new hub agent task and return its task_id.

    The response is immediate (HTTP 202 Accepted).
    Clients should subscribe to the WebSocket stream for real-time progress.
    """
    task_id = str(uuid.uuid4())
    user_id = "anonymous"  # Phase 2: extract from JWT token

    await log.ainfo(
        "hub_task_enqueued",
        task_id=task_id,
        module=body.module,
        query_length=len(body.query),
    )

    # Store initial status in Redis (TTL: 1 hour)
    redis = _get_redis()
    await redis.setex(_TASK_STATUS_KEY.format(task_id), 3600, "queued")

    # Enqueue Celery task (non-blocking)
    run_hub_agent_task.apply_async(
        kwargs={
            "task_id": task_id,
            "user_id": user_id,
            "query": body.query,
            "module": body.module,
            "user_preferences": body.user_preferences,
        },
        task_id=task_id,
    )

    return AgentRunResponse(
        task_id=task_id,
        status="queued",
        stream_url=f"ws://hub/api/v1/hub/tasks/{task_id}/stream",
    )


@router.get("/tasks/{task_id}", response_model=AgentStatusResponse)
async def get_task_status(task_id: str) -> AgentStatusResponse:
    """Poll the current status of a hub task."""
    redis = _get_redis()

    status_raw = await redis.get(_TASK_STATUS_KEY.format(task_id))
    if status_raw is None:
        return JSONResponse(status_code=404, content={"detail": "Task not found"})  # type: ignore[return-value]

    status = status_raw.decode() if isinstance(status_raw, bytes) else status_raw

    result_raw = await redis.get(_TASK_RESULT_KEY.format(task_id))
    result_text = None
    thoughts: list[str] = []
    error = None

    synergy_chains: list[dict] = []
    result_metadata: dict = {}
    if result_raw:
        result_data = json.loads(result_raw)
        result_text = result_data.get("result")
        thoughts = result_data.get("thoughts", [])
        error = result_data.get("error")
        synergy_chains = result_data.get("synergy_chains", [])
        result_metadata = result_data.get("result_metadata", {})

    return AgentStatusResponse(
        task_id=task_id,
        status=status,  # type: ignore[arg-type]
        result=result_text,
        result_metadata=result_metadata,
        error=error,
        thoughts=thoughts,
        synergy_chains=synergy_chains,
    )


@router.websocket("/tasks/{task_id}/stream")
async def stream_agent_events(websocket: WebSocket, task_id: str) -> None:
    """WebSocket endpoint — streams agent Chain-of-Thought events in real time.

    Clients connect and receive JSON event objects:
      { "type": "thought", "thought": "..." }
      { "type": "node_start", "node": "searcher" }
      { "type": "graph_done", "task_id": "..." }
    """
    await websocket.accept()
    await log.ainfo("hub_ws_connected", task_id=task_id)

    redis = _get_redis()
    pubsub = redis.pubsub()
    channel = _EVENTS_CHANNEL.format(task_id)

    try:
        await pubsub.subscribe(channel)
        async for message in _iter_pubsub(pubsub):
            await websocket.send_json(message)
            if message.get("type") in ("graph_done", "graph_error"):
                break
    except WebSocketDisconnect:
        await log.ainfo("hub_ws_disconnected", task_id=task_id)
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()


@router.post("/tasks/{task_id}/approve", response_model=HitlApprovalResponse)
async def approve_hitl(task_id: str, body: HitlApprovalRequest) -> HitlApprovalResponse:
    """Resolve a Human-in-the-Loop gate for a paused task.

    The task must be in 'awaiting_hitl' status.  Approval resumes execution;
    rejection aborts with a graceful message.
    """
    redis = _get_redis()

    status_raw = await redis.get(_TASK_STATUS_KEY.format(task_id))
    if status_raw is None:
        return JSONResponse(status_code=404, content={"detail": "Task not found"})  # type: ignore[return-value]

    status = status_raw.decode() if isinstance(status_raw, bytes) else status_raw
    if status != "awaiting_hitl":
        return JSONResponse(  # type: ignore[return-value]
            status_code=409,
            content={"detail": f"Task is not awaiting HITL (status: {status})"},
        )

    # Load saved state
    state_raw = await redis.get(_TASK_STATE_KEY.format(task_id))
    if state_raw is None:
        return JSONResponse(status_code=500, content={"detail": "Task state not found"})  # type: ignore[return-value]

    state = json.loads(state_raw)

    await log.ainfo("hub_hitl_resolved", task_id=task_id, approved=body.approved)

    # Enqueue resume task
    resume_hub_agent_task.apply_async(
        kwargs={"task_id": task_id, "state": state, "approved": body.approved},
    )

    result_status = "resumed" if body.approved else "aborted"
    return HitlApprovalResponse(
        task_id=task_id,
        approved=body.approved,
        status=result_status,  # type: ignore[arg-type]
    )


@router.post(
    "/synergy/{event_id}/dismiss",
    response_model=SynergyDismissResponse,
    summary="Dismiss a synergy suggestion (Phase 3)",
)
async def dismiss_synergy(
    event_id: str,
    body: SynergyDismissRequest,
) -> SynergyDismissResponse:
    """Log a dismissed synergy suggestion to episodic memory.

    The context hash prevents the same signal pattern from resurfacing within 7 days.
    Requires an active DB session for episodic memory persistence.
    """
    # In production this would inject the DB session and EpisodicMemory adapter.
    # The lightweight path here just logs and returns — the worker persists it
    # to hub_episodic_memory via a Celery task after the HITL rejection.
    await log.ainfo(
        "synergy_dismissed",
        event_id=event_id,
        user_id=body.user_id,
        reason=body.reason,
    )
    return SynergyDismissResponse(event_id=event_id)


@router.get("/news/articles", summary="Browse stored news articles from Qdrant")
async def list_news_articles(
    limit: int = 20,
    offset: int = 0,
    tag: str | None = None,
) -> dict:
    """Return recent articles from the Qdrant news collection (paginated).

    Does not require an OpenAI key — reads stored payloads directly.
    """
    from src.adapters.qdrant.client import get_qdrant_client
    from src.adapters.qdrant.collections import NEWS_COLLECTION

    try:
        from qdrant_client.models import FieldCondition, Filter, MatchAny
    except ImportError:
        Filter = None  # type: ignore[assignment]
        FieldCondition = None  # type: ignore[assignment]
        MatchAny = None  # type: ignore[assignment]

    client = get_qdrant_client()

    scroll_filter = None
    if tag and Filter is not None and FieldCondition is not None and MatchAny is not None:
        scroll_filter = Filter(
            must=[FieldCondition(key="tags", match=MatchAny(any=[tag]))]
        )

    try:
        scroll_result = await client.scroll(
            collection_name=NEWS_COLLECTION,
            scroll_filter=scroll_filter,
            limit=limit,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        points, _next = scroll_result
    except Exception:
        # Collection may not exist yet (first run before scraper has fired)
        return {"articles": [], "total": 0, "offset": offset}

    articles = [pt.payload for pt in points if pt.payload]
    return {"articles": articles, "total": len(articles), "offset": offset}


@router.post("/news/ask", summary="RAG chat over stored news articles")
async def news_rag_ask(body: dict) -> dict:
    """Answer a question using the stored news articles as context (RAG).

    Body: { "query": "...", "top_k": 5 }

    Requires OPENAI_API_KEY to be set for both embedding and LLM steps.
    Falls back to a plain-text summary when the key is absent.
    """
    from src.adapters.qdrant.client import get_qdrant_client
    from src.adapters.qdrant.collections import DENSE_VECTOR_NAME, NEWS_COLLECTION
    from src.config import get_settings

    query: str = body.get("query", "").strip()
    top_k: int = int(body.get("top_k", 5))

    if not query:
        return {"answer": "", "sources": []}

    settings = get_settings()
    client = get_qdrant_client()

    # ── Dense vector search via FastEmbed (local, no API key needed) ─────────
    import asyncio as _asyncio
    retrieved: list[dict] = []
    try:
        from fastembed import TextEmbedding as _TextEmbedding
        _fe = _TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        loop = _asyncio.get_event_loop()
        dense_vec = await loop.run_in_executor(
            None, lambda: [float(v) for v in list(_fe.embed([query[:2000]]))[0]]
        )
        results = await client.search(
            collection_name=NEWS_COLLECTION,
            query_vector=(DENSE_VECTOR_NAME, dense_vec),
            limit=top_k,
            with_payload=True,
        )
        retrieved = [pt.payload for pt in results if pt.payload]
    except Exception as exc:
        log.warning("news_rag_search_error", error=str(exc))

    if not retrieved:
        return {
            "answer": "No relevant articles found. The news scraper runs every 30 minutes — check back soon.",
            "sources": [],
        }

    # ── Build prompt context ───────────────────────────────────────────────────
    context_parts: list[str] = []
    sources: list[dict] = []
    for i, art in enumerate(retrieved, 1):
        title = art.get("title", "")
        summary = art.get("summary", "")
        domain = art.get("source_domain", "")
        url = art.get("url", "")
        context_parts.append(f"[{i}] {title}\nSource: {domain}\nSummary: {summary}")
        sources.append({"title": title, "url": url, "source_domain": domain})

    context = "\n\n".join(context_parts)

    # ── LLM answer: try OpenAI → Ollama → extractive fallback ─────────────────
    answer = ""

    if not answer and settings.openai_api_key:
        try:
            from openai import AsyncOpenAI
            oai = AsyncOpenAI(api_key=settings.openai_api_key)
            chat_resp = await oai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a news analyst. Answer based ONLY on the provided articles. Be concise. Cite sources [1],[2] etc."},
                    {"role": "user", "content": f"Articles:\n{context}\n\nQuestion: {query}"},
                ],
                max_tokens=512,
                temperature=0.3,
            )
            answer = chat_resp.choices[0].message.content or ""
        except Exception as exc:
            log.warning("news_rag_openai_error", error=str(exc))

    if not answer:
        try:
            from src.config import get_settings as _gs
            _s = _gs()
            import httpx as _httpx
            ollama_host = getattr(_s, "ollama_host", "http://ollama:11434").rstrip("/")
            async with _httpx.AsyncClient(timeout=60.0) as _c:
                prompt = (
                    f"You are a news analyst. Answer the question based ONLY on these articles:\n\n"
                    f"{context}\n\nQuestion: {query}\n\nAnswer concisely in 2-4 sentences:"
                )
                resp = await _c.post(
                    f"{ollama_host}/api/generate",
                    json={"model": "llama3.2:3b", "prompt": prompt, "stream": False},
                )
                if resp.status_code == 200:
                    answer = resp.json().get("response", "")
        except Exception as exc:
            log.warning("news_rag_ollama_error", error=str(exc))

    if not answer:
        # Last resort: plain list of summaries
        answer = f"Found {len(retrieved)} relevant articles:\n\n" + "\n\n".join(
            f"[{i}] {art.get('title', '')} ({art.get('source_domain', '')})\n{art.get('summary', '')}"
            for i, art in enumerate(retrieved, 1)
        )

    return {"answer": answer, "sources": sources}


async def _iter_pubsub(pubsub: object) -> AsyncGenerator[dict[str, object], None]:
    """Async generator over Redis pub/sub messages, yielding parsed JSON dicts."""
    async for raw_message in pubsub.listen():  # type: ignore[attr-defined]
        if raw_message["type"] != "message":
            continue
        data = raw_message.get("data", b"")
        if isinstance(data, bytes):
            data = data.decode()
        try:
            yield json.loads(data)
        except (json.JSONDecodeError, TypeError):
            continue
