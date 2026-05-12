"""Celery signal handlers for observability:

- task_prerun: propagate correlation_id from task kwargs into structlog context
- task_failure: publish failure event to Redis for SSE toast delivery
- task_prerun: redact secret fields from logged task kwargs
"""

from __future__ import annotations

import json
import re
from typing import Any

import structlog
from celery.signals import task_failure, task_prerun, task_postrun

log = structlog.get_logger(__name__)

# Patterns whose VALUES should be replaced in log output
_SECRET_PATTERN = re.compile(
    r"(_key|_token|_secret|_password|api_key|access_key|secret_key)$",
    re.IGNORECASE,
)


def _redact(obj: Any, depth: int = 0) -> Any:
    """Recursively redact sensitive values from dicts up to depth 3."""
    if depth > 3:
        return obj
    if isinstance(obj, dict):
        return {
            k: "[REDACTED]" if _SECRET_PATTERN.search(str(k)) else _redact(v, depth + 1)
            for k, v in obj.items()
        }
    if isinstance(obj, (list, tuple)):
        return type(obj)(_redact(i, depth + 1) for i in obj)
    return obj


@task_prerun.connect
def on_task_prerun(task_id: str, task, args, kwargs, **extras) -> None:  # type: ignore[misc]
    """Bind correlation_id from kwargs into structlog context and log redacted args."""
    correlation_id = (kwargs or {}).get("correlation_id", "")
    structlog.contextvars.bind_contextvars(
        task_id=task_id,
        task_name=task.name,
        correlation_id=correlation_id,
    )
    safe_kwargs = _redact(kwargs or {})
    log.debug("task_started", task=task.name, kwargs=safe_kwargs)


@task_failure.connect
def on_task_failure(
    task_id: str,
    exception: Exception,
    traceback,
    einfo,
    args,
    kwargs,
    **extras,
) -> None:
    """Publish a task failure event to Redis so the SSE endpoint can forward a toast."""
    log.error(
        "task_failed",
        task_id=task_id,
        error=str(exception),
        error_type=type(exception).__name__,
    )
    try:
        import redis as sync_redis
        from src.config import get_settings

        settings = get_settings()
        r = sync_redis.from_url(settings.redis_url, decode_responses=True)
        payload = json.dumps({
            "type": "task_failure",
            "task_id": task_id,
            "error": str(exception)[:200],
            "correlation_id": (kwargs or {}).get("correlation_id", ""),
        })
        r.publish("celery:failures", payload)
        r.close()
    except Exception:
        pass  # Never let observability crash a worker


@task_postrun.connect
def on_task_postrun(task_id: str, task, **extras) -> None:  # type: ignore[misc]
    """Clear structlog context vars after each task to avoid leaking into next task."""
    structlog.contextvars.clear_contextvars()
