"""LangSmith tracing adapter — per-node timing, token cost, and retrieval inspection.

Design:
- All tracing is opt-in via LANGSMITH_API_KEY env var (no-op when not set)
- Structured as a context manager decorator for agent node functions
- Records: node name, duration_ms, input/output sizes, error info
- Uses structlog for local fallback when LangSmith is unavailable

Per PRD: every agent graph execution must be traceable end-to-end in LangSmith.
"""

from __future__ import annotations

import functools
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Callable

import structlog

log = structlog.get_logger(__name__)


class LangSmithTracer:
    """Lightweight LangSmith trace emitter.

    When LANGSMITH_API_KEY is not set or the langsmith SDK is not installed,
    all methods are no-ops — the agent pipeline is never blocked by tracing.

    Args:
        project_name: LangSmith project to log runs to.
        api_key:      LangSmith API key (from settings).
        enabled:      Explicitly disable even if key is present.
    """

    def __init__(
        self,
        project_name: str = "hub-agent",
        api_key: str | None = None,
        enabled: bool = True,
    ) -> None:
        self._project = project_name
        self._enabled = enabled and bool(api_key)
        self._client: Any = None

        if self._enabled:
            try:
                from langsmith import Client  # noqa: PLC0415
                self._client = Client(api_key=api_key)
                log.info("langsmith_tracer_initialized", project=project_name)
            except ImportError:
                log.warning("langsmith_not_installed", detail="pip install langsmith")
                self._enabled = False

    @asynccontextmanager
    async def trace_node(
        self,
        run_id: str,
        node_name: str,
        inputs: dict[str, Any] | None = None,
    ) -> AsyncGenerator[None, None]:
        """Async context manager that wraps a single agent node execution.

        Usage::
            async with tracer.trace_node(task_id, "searcher", inputs=state):
                result = await searcher_agent(state)
        """
        start = time.monotonic()
        error: str | None = None

        try:
            yield
        except Exception as exc:
            error = str(exc)
            raise
        finally:
            duration_ms = round((time.monotonic() - start) * 1000, 2)
            await self._emit(
                run_id=run_id,
                node_name=node_name,
                duration_ms=duration_ms,
                inputs=inputs or {},
                error=error,
            )

    async def trace_graph(
        self,
        run_id: str,
        module: str,
        user_id: str,
    ) -> None:
        """Record start of a full graph run."""
        await self._emit(
            run_id=run_id,
            node_name="graph_start",
            duration_ms=0,
            inputs={"module": module, "user_id": user_id},
        )

    async def trace_retrieval(
        self,
        run_id: str,
        query: str,
        retrieved_chunks: list[dict[str, Any]],
        latency_ms: float,
    ) -> None:
        """Record a Qdrant retrieval event with chunk metadata."""
        await self._emit(
            run_id=run_id,
            node_name="qdrant_retrieval",
            duration_ms=latency_ms,
            inputs={"query": query[:200]},
            outputs={
                "chunk_count": len(retrieved_chunks),
                "top_score": retrieved_chunks[0].get("score", 0) if retrieved_chunks else 0,
            },
        )

    async def _emit(
        self,
        run_id: str,
        node_name: str,
        duration_ms: float,
        inputs: dict[str, Any],
        outputs: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """Emit a trace event — LangSmith if enabled, structlog always."""
        await log.ainfo(
            "agent_trace",
            run_id=run_id,
            node=node_name,
            duration_ms=duration_ms,
            error=error,
        )

        if not self._enabled or self._client is None:
            return

        try:
            # LangSmith SDK run creation (non-blocking best-effort)
            self._client.create_run(
                name=node_name,
                run_type="chain",
                project_name=self._project,
                inputs=inputs,
                outputs=outputs or {},
                error=error,
                extra={"duration_ms": duration_ms, "run_id": run_id},
            )
        except Exception as exc:
            # Tracing must never break the pipeline
            await log.awarning("langsmith_emit_error", error=str(exc))


def traced_node(node_name: str) -> Callable:
    """Decorator factory: wraps an async agent node function with LangSmith tracing.

    Usage::
        @traced_node("searcher")
        async def news_searcher_agent(state, ...):
            ...

    The tracer instance must be available via `state.get("_tracer")` or the
    decorator is a transparent pass-through.
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def wrapper(state: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
            tracer: LangSmithTracer | None = state.get("_tracer")  # type: ignore[assignment]
            run_id = state.get("task_id", "unknown")

            if tracer is None:
                return await fn(state, **kwargs)

            async with tracer.trace_node(run_id, node_name, inputs={"query": state.get("query", "")[:200]}):
                return await fn(state, **kwargs)

        return wrapper
    return decorator


_default_tracer: LangSmithTracer | None = None


def get_tracer() -> LangSmithTracer:
    """Return the singleton LangSmithTracer, initialised from settings."""
    global _default_tracer
    if _default_tracer is None:
        try:
            from src.config import get_settings  # noqa: PLC0415
            settings = get_settings()
            _default_tracer = LangSmithTracer(
                project_name=getattr(settings, "langsmith_project", "hub-agent"),
                api_key=getattr(settings, "langsmith_api_key", None),
            )
        except Exception:
            _default_tracer = LangSmithTracer(enabled=False)
    return _default_tracer
