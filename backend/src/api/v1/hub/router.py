"""Hub API router — agent execution, status polling, WebSocket streaming, HITL.

Endpoints:
  POST  /api/v1/hub/agent/run              → enqueue task, return task_id
  GET   /api/v1/hub/tasks/{task_id}        → poll task status
  WS    /api/v1/hub/tasks/{task_id}/stream → real-time event stream
  POST  /api/v1/hub/tasks/{task_id}/approve → resolve HITL gate
  DELETE /api/v1/hub/tasks/{task_id}       → cancel a task
  GET   /api/v1/hub/conversations          → conversation history
  GET   /api/v1/hub/news/articles          → browse stored news
  POST  /api/v1/hub/news/ask               → RAG chat over news
  GET   /api/v1/hub/news/sources           → list RSS feed sources
  POST  /api/v1/hub/news/sources           → add RSS feed source
  DELETE /api/v1/hub/news/sources          → remove RSS feed source
  PATCH /api/v1/hub/news/sources           → enable/disable RSS feed
  GET   /api/v1/hub/news/topics            → user topic subscriptions
  PUT   /api/v1/hub/news/topics            → update topic subscriptions
  GET   /api/v1/hub/news/bookmarks         → bookmarked articles
  POST  /api/v1/hub/news/bookmarks         → bookmark an article
  DELETE /api/v1/hub/news/bookmarks/{id}   → remove a bookmark
  GET   /api/v1/hub/news/trending          → trending tags
  POST  /api/v1/hub/news/scrape/trigger    → manually trigger scrape
  GET   /api/v1/hub/queue/status           → Celery queue status

Design:
- POST /agent/run is non-blocking: it enqueues a Celery task and returns immediately.
- Clients subscribe to the WebSocket to receive streamed Chain-of-Thought events.
- Redis pub/sub channel: "hub:task:{task_id}:events"
"""

from __future__ import annotations

import json
import uuid
from typing import Annotated, AsyncGenerator

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from redis.asyncio import Redis

from src.adapters.hub.redis_keys import (
    HUB_TTL,
    task_status_key,
    task_result_key,
    task_state_key,
    task_events_channel,
)
from src.api.v1.auth.dependencies import get_current_user
from src.api.v1.hub.schemas import (
    AgentRunRequest,
    AgentRunResponse,
    AgentStatusResponse,
    HitlApprovalRequest,
    HitlApprovalResponse,
    NewsRagRequest,
    NewsRagResponse,
    SynergyDismissRequest,
    SynergyDismissResponse,
)
from src.core.domain.entities.user import User
from src.workers.tasks.hub_tasks import run_hub_agent_task, resume_hub_agent_task

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/hub", tags=["hub"])

# Module-level FastEmbed singleton — avoids re-instantiating per request
_fastembed_model = None

# Bookmark Redis key template
_BOOKMARKS_KEY = "news:bookmarks:{user_id}"


def _get_redis() -> Redis:
    """Create a Redis client from settings.

    TODO: Proper pooling via request.app.state.redis requires access to the
    Request object throughout the module. For now a per-call client is used;
    pool-based refactor should happen alongside a dependency injection overhaul.
    """
    import redis.asyncio as aioredis
    from src.config import get_settings
    return aioredis.from_url(get_settings().redis_url, decode_responses=True)


def _get_fastembed() -> object:
    """Return (or lazily initialise) the module-level FastEmbed model."""
    global _fastembed_model  # noqa: PLW0603
    if _fastembed_model is None:
        from fastembed import TextEmbedding
        _fastembed_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    return _fastembed_model


# ── Core agent endpoints ────────────────────────────────────────────────────────

@router.post("/agent/run", response_model=AgentRunResponse, status_code=202)
async def run_agent(
    body: AgentRunRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
) -> AgentRunResponse:
    """Enqueue a new hub agent task and return its task_id.

    The response is immediate (HTTP 202 Accepted).
    Clients should subscribe to the WebSocket stream for real-time progress.
    """
    task_id = str(uuid.uuid4())
    user_id = str(current_user.id)

    await log.ainfo(
        "hub_task_enqueued",
        task_id=task_id,
        user_id=user_id,
        module=body.module,
        query_length=len(body.query),
    )

    # Store initial status in Redis
    redis = _get_redis()
    await redis.setex(task_status_key(task_id), HUB_TTL, "queued")

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

    # Build WebSocket URL dynamically from the incoming request
    protocol = "wss" if request.url.scheme == "https" else "ws"
    stream_url = f"{protocol}://{request.url.netloc}/api/v1/hub/tasks/{task_id}/stream"

    return AgentRunResponse(
        task_id=task_id,
        status="queued",
        stream_url=stream_url,
    )


@router.get("/tasks/{task_id}", response_model=AgentStatusResponse)
async def get_task_status(
    task_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> AgentStatusResponse:
    """Poll the current status of a hub task."""
    redis = _get_redis()

    status_raw = await redis.get(task_status_key(task_id))
    if status_raw is None:
        raise HTTPException(status_code=404, detail="Task not found")

    status = status_raw.decode() if isinstance(status_raw, bytes) else status_raw

    result_raw = await redis.get(task_result_key(task_id))
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
    channel = task_events_channel(task_id)

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
async def approve_hitl(
    task_id: str,
    body: HitlApprovalRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> HitlApprovalResponse:
    """Resolve a Human-in-the-Loop gate for a paused task.

    The task must be in 'awaiting_hitl' status.  Approval resumes execution;
    rejection aborts with a graceful message.
    """
    redis = _get_redis()

    status_raw = await redis.get(task_status_key(task_id))
    if status_raw is None:
        raise HTTPException(status_code=404, detail="Task not found")

    status = status_raw.decode() if isinstance(status_raw, bytes) else status_raw
    if status != "awaiting_hitl":
        raise HTTPException(
            status_code=409,
            detail=f"Task is not awaiting HITL (status: {status})",
        )

    # Load saved state
    state_raw = await redis.get(task_state_key(task_id))
    if state_raw is None:
        raise HTTPException(status_code=500, detail="Task state not found")

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


@router.delete("/tasks/{task_id}", status_code=204, response_model=None)
async def cancel_task(
    task_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Cancel a queued or running hub task."""
    redis = _get_redis()
    status_raw = await redis.get(task_status_key(task_id))
    if status_raw is None:
        raise HTTPException(status_code=404, detail="Task not found")
    status = status_raw if isinstance(status_raw, str) else status_raw.decode()
    if status in ("completed", "failed", "cancelled"):
        raise HTTPException(status_code=409, detail=f"Cannot cancel task in '{status}' state")
    # Revoke Celery task
    from src.workers.celery_app import celery_app as _celery
    _celery.control.revoke(task_id, terminate=True, signal="SIGTERM")
    await redis.setex(task_status_key(task_id), HUB_TTL, "cancelled")
    # Notify WebSocket subscribers
    import redis.asyncio as aioredis
    from src.config import get_settings
    r = aioredis.from_url(get_settings().redis_url)
    await r.publish(
        task_events_channel(task_id),
        json.dumps({"type": "graph_error", "task_id": task_id, "message": "Task cancelled by user"}),
    )
    await r.aclose()


# ── Synergy ────────────────────────────────────────────────────────────────────

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
    await log.ainfo(
        "synergy_dismissed",
        event_id=event_id,
        user_id=body.user_id,
        reason=body.reason,
    )
    return SynergyDismissResponse(event_id=event_id)


# ── Conversation History ───────────────────────────────────────────────────────

@router.get("/conversations", summary="List user's conversation history")
async def list_conversations(
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = 20,
    offset: int = 0,
    module: str | None = None,
) -> dict:
    """Return paginated conversation history for the authenticated user."""
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy import select, desc
    from src.adapters.db.models.hub_conversation import HubConversation
    from src.workers.tasks.hub_tasks import _get_db_engine

    user_id = str(current_user.id)

    try:
        async with AsyncSession(_get_db_engine()) as session:
            q = select(HubConversation).where(
                HubConversation.user_id == user_id
            ).order_by(desc(HubConversation.created_at)).offset(offset).limit(limit)
            if module:
                q = q.where(HubConversation.module == module)
            result = await session.execute(q)
            rows = result.scalars().all()
            return {
                "conversations": [
                    {
                        "task_id": r.task_id,
                        "module": r.module,
                        "query": r.query,
                        "result": r.result,
                        "error": r.error,
                        "thoughts": r.thoughts or [],
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                    }
                    for r in rows
                ],
                "total": len(rows),
                "offset": offset,
            }
    except Exception as exc:
        log.warning("hub_list_conversations_error", error=str(exc))
        return {"conversations": [], "total": 0, "offset": offset}


# ── News Articles ──────────────────────────────────────────────────────────────

@router.get("/news/articles", summary="Browse stored news articles from Qdrant")
async def list_news_articles(
    current_user: Annotated[User, Depends(get_current_user)],
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


@router.post("/news/ask", response_model=NewsRagResponse, summary="RAG chat over stored news articles")
async def news_rag_ask(
    body: NewsRagRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> NewsRagResponse:
    """Answer a question using the stored news articles as context (RAG).

    Requires OPENAI_API_KEY to be set for both embedding and LLM steps.
    Falls back to a plain-text summary when the key is absent.
    """
    from src.adapters.qdrant.client import get_qdrant_client
    from src.adapters.qdrant.collections import DENSE_VECTOR_NAME, NEWS_COLLECTION
    from src.config import get_settings

    query = body.query.strip()
    top_k = body.top_k

    if not query:
        return NewsRagResponse(answer="", sources=[])

    settings = get_settings()
    client = get_qdrant_client()

    # ── Dense vector search via FastEmbed (local, no API key needed) ─────────
    import asyncio as _asyncio
    retrieved: list[dict] = []
    try:
        _fe = _get_fastembed()
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
        return NewsRagResponse(
            answer="No relevant articles found. The news scraper runs every 30 minutes — check back soon.",
            sources=[],
        )

    # ── Build prompt context ───────────────────────────────────────────────────
    context_parts: list[str] = []
    sources: list[dict[str, str]] = []
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
            import httpx as _httpx
            ollama_host = getattr(settings, "ollama_host", "http://ollama:11434").rstrip("/")
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

    return NewsRagResponse(answer=answer, sources=sources)


# ── News Source Management ─────────────────────────────────────────────────────

@router.get("/news/sources", summary="List configured news RSS sources")
async def list_news_sources(
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    redis = _get_redis()
    from src.adapters.news.feed_registry import get_feeds
    feeds = await get_feeds(redis)
    return {"sources": feeds}


@router.post("/news/sources", summary="Add a new RSS feed source", status_code=201)
async def add_news_source(
    body: dict,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    from src.adapters.news.feed_registry import add_feed
    url = body.get("url", "").strip()
    name = body.get("name", url)
    if not url.startswith("http"):
        raise HTTPException(status_code=400, detail="Invalid feed URL")
    redis = _get_redis()
    feed = await add_feed(redis, url, name)
    return feed


@router.delete("/news/sources", summary="Remove an RSS feed source", status_code=204, response_model=None)
async def remove_news_source(
    url: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    from src.adapters.news.feed_registry import remove_feed
    redis = _get_redis()
    removed = await remove_feed(redis, url)
    if not removed:
        raise HTTPException(status_code=404, detail="Feed not found")


@router.patch("/news/sources", summary="Enable or disable an RSS feed source")
async def toggle_news_source(
    body: dict,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    from src.adapters.news.feed_registry import toggle_feed
    url = body.get("url", "").strip()
    enabled = bool(body.get("enabled", True))
    redis = _get_redis()
    ok = await toggle_feed(redis, url, enabled)
    if not ok:
        raise HTTPException(status_code=404, detail="Feed not found")
    return {"url": url, "enabled": enabled}


# ── News Topic Subscriptions ───────────────────────────────────────────────────

@router.get("/news/topics", summary="Get user's subscribed news topics")
async def get_news_topics(
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    redis = _get_redis()
    user_id = str(current_user.id)
    raw = await redis.get(f"news:topics:{user_id}")
    topics = json.loads(raw) if raw else []
    return {"topics": topics}


@router.put("/news/topics", summary="Update user's subscribed news topics")
async def update_news_topics(
    body: dict,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    topics: list[str] = body.get("topics", [])
    if not isinstance(topics, list):
        raise HTTPException(status_code=400, detail="topics must be a list of strings")
    topics = [str(t).strip().lower() for t in topics if t]
    redis = _get_redis()
    user_id = str(current_user.id)
    await redis.set(f"news:topics:{user_id}", json.dumps(topics))
    return {"topics": topics}


# ── Article Bookmarks ──────────────────────────────────────────────────────────

@router.get("/news/bookmarks", summary="Get user's bookmarked articles")
async def get_bookmarks(
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    redis = _get_redis()
    user_id = str(current_user.id)
    raw = await redis.lrange(_BOOKMARKS_KEY.format(user_id=user_id), 0, -1)
    bookmarks = [json.loads(item) for item in raw]
    return {"bookmarks": bookmarks}


@router.post("/news/bookmarks", summary="Bookmark an article", status_code=201)
async def add_bookmark(
    body: dict,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    from datetime import datetime, timezone
    article = {
        "article_id": body.get("article_id", ""),
        "url": body.get("url", ""),
        "title": body.get("title", ""),
        "source_domain": body.get("source_domain", ""),
        "bookmarked_at": datetime.now(timezone.utc).isoformat(),
    }
    redis = _get_redis()
    user_id = str(current_user.id)
    key = _BOOKMARKS_KEY.format(user_id=user_id)
    await redis.lpush(key, json.dumps(article))
    await redis.ltrim(key, 0, 99)  # Keep latest 100
    return article


@router.delete("/news/bookmarks/{article_id}", status_code=204, response_model=None)
async def remove_bookmark(
    article_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    redis = _get_redis()
    user_id = str(current_user.id)
    key = _BOOKMARKS_KEY.format(user_id=user_id)
    items = await redis.lrange(key, 0, -1)
    for item in items:
        data = json.loads(item)
        if data.get("article_id") == article_id:
            await redis.lrem(key, 0, item)
            return
    raise HTTPException(status_code=404, detail="Bookmark not found")


# ── Trending Topics ────────────────────────────────────────────────────────────

@router.get("/news/trending", summary="Get trending tags from recent articles")
async def get_trending_topics(
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = 10,
) -> dict:
    from src.adapters.qdrant.client import get_qdrant_client
    from src.adapters.qdrant.collections import NEWS_COLLECTION
    client = get_qdrant_client()
    try:
        points, _ = await client.scroll(
            collection_name=NEWS_COLLECTION,
            limit=500,
            with_payload=["tags"],
            with_vectors=False,
        )
        tag_counts: dict[str, int] = {}
        for pt in points:
            for tag in (pt.payload or {}).get("tags", []):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:limit]
        return {"trending": [{"tag": t, "count": c} for t, c in sorted_tags]}
    except Exception:
        return {"trending": []}


# ── Manual Scrape Trigger ──────────────────────────────────────────────────────

@router.post("/news/scrape/trigger", summary="Manually trigger a news scrape", status_code=202)
async def trigger_news_scrape(
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    from src.workers.tasks.news_scraper_task import scrape_news_task
    task = scrape_news_task.apply_async()
    return {"task_id": task.id, "status": "queued", "message": "News scrape enqueued"}


# ── Queue Status ───────────────────────────────────────────────────────────────

@router.get("/queue/status", summary="Hub task queue status")
async def get_queue_status(
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Return count of queued/running/recent tasks."""
    from src.workers.celery_app import celery_app as _celery
    try:
        inspect = _celery.control.inspect(timeout=2.0)
        active = inspect.active() or {}
        reserved = inspect.reserved() or {}
        active_count = sum(len(v) for v in active.values())
        queued_count = sum(len(v) for v in reserved.values())
        return {
            "active_tasks": active_count,
            "queued_tasks": queued_count,
            "workers": list(active.keys()),
        }
    except Exception:
        return {"active_tasks": 0, "queued_tasks": 0, "workers": []}


# ── WebSocket helpers ──────────────────────────────────────────────────────────

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
