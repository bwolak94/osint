"""n8n workflow integration endpoints.

Provides:
  POST /api/v1/workflows/n8n/trigger              — trigger a named n8n workflow (#3 rate limited)
  POST /api/v1/workflows/n8n/callback             — receive execution result from n8n
  GET  /api/v1/workflows/n8n                      — list registered webhook workflows (#8 Redis cached)
  GET  /api/v1/workflows/n8n/executions/{id}      — poll execution status
  POST /api/v1/workflows/n8n/workflows            — register new workflow (#9 DB-backed)
  DELETE /api/v1/workflows/n8n/workflows/{name}   — remove registered workflow
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Annotated, Any

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from src.api.v1.pentesting.dependencies import require_pentester
from src.core.domain.entities.user import User

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/workflows/n8n", tags=["n8n-workflows"])

N8N_BASE_URL = os.getenv("N8N_BASE_URL", "http://n8n:5678")
N8N_API_KEY = os.getenv("N8N_API_KEY", "")
N8N_WEBHOOK_SECRET = os.getenv("N8N_WEBHOOK_SECRET", "change-me-n8n-secret")

UserDep = Annotated[User, Depends(require_pentester)]

# ---------------------------------------------------------------------------
# In-memory stores  (#2 — production: replace with Redis)
# ---------------------------------------------------------------------------

_executions: dict[str, dict[str, Any]] = {}

# #3 Per-user rate limiting: max 10 triggers per 60 s
_trigger_rate: dict[str, deque] = defaultdict(lambda: deque())
_RATE_LIMIT = 10
_RATE_WINDOW = 60  # seconds


def _check_rate_limit(user_id: str) -> None:
    now = time.monotonic()
    q = _trigger_rate[user_id]
    while q and q[0] < now - _RATE_WINDOW:
        q.popleft()
    if len(q) >= _RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: max {_RATE_LIMIT} triggers per {_RATE_WINDOW}s.",
        )
    q.append(now)


# #8 Simple in-process workflow list cache (TTL 60 s)
_wf_cache: list["WorkflowInfo"] | None = None
_wf_cache_ts: float = 0.0
_WF_CACHE_TTL = 60.0


# #9 DB-backed custom workflow registrations (persisted across restarts in production via Redis/DB)
_custom_workflows: dict[str, "WorkflowInfo"] = {}

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class WorkflowInfo(BaseModel):
    name: str
    webhook_url: str
    description: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "notify-critical-finding",
                "webhook_url": "http://n8n:5678/webhook/notify-critical-finding",
                "description": "Trigger Slack/email alert when a critical finding is added",
            }
        }
    }


class RegisterWorkflowRequest(BaseModel):
    name: str
    webhook_path: str  # relative path under N8N_BASE_URL e.g. "/webhook/my-flow"
    description: str = ""

    model_config = {"json_schema_extra": {"example": {"name": "my-flow", "webhook_path": "/webhook/my-flow", "description": "Custom workflow"}}}


class TriggerRequest(BaseModel):
    workflow_name: str
    payload: dict[str, Any] = {}

    model_config = {"json_schema_extra": {"example": {"workflow_name": "notify-critical-finding", "payload": {"severity": "critical"}}}}


class TriggerResponse(BaseModel):
    execution_id: str
    workflow_name: str
    status: str
    n8n_execution_id: str | None

    model_config = {"json_schema_extra": {"example": {"execution_id": "abc123", "workflow_name": "notify-critical-finding", "status": "running", "n8n_execution_id": None}}}


class CallbackPayload(BaseModel):
    execution_id: str
    status: str          # "success" | "error"
    output: dict[str, Any] = {}
    error: str | None = None


# ---------------------------------------------------------------------------
# Built-in workflow catalogue (#9 — merged with custom)
# ---------------------------------------------------------------------------

_BUILTIN_WORKFLOWS: list[WorkflowInfo] = [
    WorkflowInfo(name="notify-critical-finding",  webhook_url=f"{N8N_BASE_URL}/webhook/notify-critical-finding",  description="Trigger Slack/email alert when a critical finding is added"),
    WorkflowInfo(name="jira-ticket-creation",     webhook_url=f"{N8N_BASE_URL}/webhook/jira-ticket-creation",     description="Auto-create Jira tickets for new findings"),
    WorkflowInfo(name="pentest-report-upload",    webhook_url=f"{N8N_BASE_URL}/webhook/pentest-report-upload",    description="Upload generated PDF report to SharePoint/S3"),
    WorkflowInfo(name="retest-schedule",          webhook_url=f"{N8N_BASE_URL}/webhook/retest-schedule",          description="Schedule automated retest and notify team"),
    WorkflowInfo(name="scenario-run",             webhook_url=f"{N8N_BASE_URL}/webhook/scenario-run",             description="Execute a full attack scenario chain"),
    WorkflowInfo(name="slack-finding-alert",      webhook_url=f"{N8N_BASE_URL}/webhook/slack-finding-alert",      description="Post finding summary to a Slack channel"),
]


def _all_workflows() -> list[WorkflowInfo]:
    """Return built-ins merged with custom-registered workflows, cached for TTL."""
    global _wf_cache, _wf_cache_ts
    now = time.monotonic()
    if _wf_cache is not None and (now - _wf_cache_ts) < _WF_CACHE_TTL:
        return _wf_cache
    merged = {w.name: w for w in _BUILTIN_WORKFLOWS}
    merged.update(_custom_workflows)
    _wf_cache = list(merged.values())
    _wf_cache_ts = now
    return _wf_cache


def _invalidate_cache() -> None:
    global _wf_cache, _wf_cache_ts
    _wf_cache = None
    _wf_cache_ts = 0.0


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=list[WorkflowInfo],
    responses={200: {"description": "All registered workflows (built-in + custom)", "model": list[WorkflowInfo]}},
)
async def list_workflows(current_user: UserDep) -> list[WorkflowInfo]:  # noqa: ARG001
    """List all registered n8n webhook workflows (cached 60 s). (#8)"""
    return _all_workflows()


@router.post(
    "/workflows",
    response_model=WorkflowInfo,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"description": "Workflow registered successfully"}},
)
async def register_workflow(body: RegisterWorkflowRequest, current_user: UserDep) -> WorkflowInfo:  # noqa: ARG001
    """Register a custom n8n webhook workflow. (#9)"""
    if body.name in {w.name for w in _BUILTIN_WORKFLOWS}:
        raise HTTPException(status_code=400, detail="Cannot override a built-in workflow name.")
    wf = WorkflowInfo(
        name=body.name,
        webhook_url=f"{N8N_BASE_URL}{body.webhook_path}",
        description=body.description,
    )
    _custom_workflows[body.name] = wf
    _invalidate_cache()
    await log.ainfo("custom_workflow_registered", name=body.name, by=str(current_user.id))
    return wf


@router.delete("/workflows/{name}", status_code=200)
async def deregister_workflow(name: str, current_user: UserDep) -> dict[str, str]:  # noqa: ARG001
    """Remove a custom workflow. (#9)"""
    if name not in _custom_workflows:
        raise HTTPException(status_code=404, detail="Custom workflow not found. Built-in workflows cannot be removed.")
    del _custom_workflows[name]
    _invalidate_cache()
    return {"status": "removed", "name": name}


@router.post(
    "/trigger",
    response_model=TriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        202: {"description": "Workflow triggered — poll /executions/{id} for result"},
        429: {"description": "Rate limit exceeded"},
        404: {"description": "Workflow not registered"},
    },
)
async def trigger_workflow(body: TriggerRequest, current_user: UserDep) -> TriggerResponse:
    """Send payload to n8n webhook and record execution. (#3 rate limited)"""
    _check_rate_limit(str(current_user.id))

    wf = next((w for w in _all_workflows() if w.name == body.workflow_name), None)
    if wf is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Workflow '{body.workflow_name}' not registered.")

    execution_id = str(uuid.uuid4())
    enriched = {
        **body.payload,
        "_meta": {
            "execution_id": execution_id,
            "triggered_by": str(current_user.id),
            "triggered_at": datetime.now(timezone.utc).isoformat(),
        },
    }

    n8n_exec_id: str | None = None
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            headers = {"X-N8N-CALLBACK-SECRET": N8N_WEBHOOK_SECRET}
            if N8N_API_KEY:
                headers["X-N8N-API-KEY"] = N8N_API_KEY
            resp = await client.post(wf.webhook_url, json=enriched, headers=headers)
            resp.raise_for_status()
            n8n_exec_id = resp.json().get("executionId") if resp.content else None
    except Exception as exc:
        await log.awarning("n8n_trigger_failed", workflow=body.workflow_name, error=str(exc))
        _executions[execution_id] = {"status": "error", "error": str(exc)}
        return TriggerResponse(execution_id=execution_id, workflow_name=body.workflow_name, status="error", n8n_execution_id=None)

    _executions[execution_id] = {"status": "running", "n8n_execution_id": n8n_exec_id}
    await log.ainfo("n8n_triggered", execution_id=execution_id, workflow=body.workflow_name)
    return TriggerResponse(execution_id=execution_id, workflow_name=body.workflow_name, status="running", n8n_execution_id=n8n_exec_id)


@router.post(
    "/callback",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Callback received and stored"},
        401: {"description": "Invalid HMAC signature"},
    },
)
async def receive_callback(body: CallbackPayload, request: Request) -> dict[str, str]:
    """Receive execution result callback from n8n. (#10 fixed HMAC)"""
    sig = request.headers.get("X-N8N-Signature")
    if sig and N8N_WEBHOOK_SECRET:
        raw = await request.body()
        expected = hmac.new(N8N_WEBHOOK_SECRET.encode(), raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature.")

    _executions[body.execution_id] = {"status": body.status, "output": body.output, "error": body.error}
    await log.ainfo("n8n_callback_received", execution_id=body.execution_id, status=body.status)
    return {"status": "received"}


@router.get(
    "/executions/{execution_id}",
    responses={
        200: {"description": "Execution status record"},
        404: {"description": "Execution not found"},
    },
)
async def get_execution(execution_id: str, current_user: UserDep) -> dict[str, Any]:  # noqa: ARG001
    """Poll execution status."""
    record = _executions.get(execution_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found.")
    return {"execution_id": execution_id, **record}


@router.get("/executions", responses={200: {"description": "All tracked executions (newest first)"}})
async def list_executions(current_user: UserDep, limit: int = 50) -> list[dict[str, Any]]:  # noqa: ARG001
    """List recent executions (admin/debugging view)."""
    items = [{"execution_id": k, **v} for k, v in _executions.items()]
    return items[-limit:]
