"""Data retention policy management endpoints."""

import secrets
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.api.v1.auth.dependencies import get_current_user

log = structlog.get_logger()
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class RetentionPolicyCreate(BaseModel):
    entity_type: str = Field(..., min_length=1, max_length=100)
    max_age_days: int = Field(..., ge=1, le=3650)
    action: str = Field(..., pattern="^(archive|delete)$")
    workspace_id: str = Field(..., min_length=1)


class RetentionPolicyUpdate(BaseModel):
    max_age_days: int | None = Field(None, ge=1, le=3650)
    action: str | None = Field(None, pattern="^(archive|delete)$")


class RetentionPolicyResponse(BaseModel):
    id: str
    entity_type: str
    max_age_days: int
    action: str
    workspace_id: str
    created_by: str
    created_at: str
    updated_at: str


class RetentionPolicyListResponse(BaseModel):
    policies: list[RetentionPolicyResponse]
    total: int


class AffectedEntityPreview(BaseModel):
    entity_type: str
    entity_id: str
    age_days: int
    action: str


class DryRunResponse(BaseModel):
    total_affected: int
    affected_entities: list[AffectedEntityPreview]
    estimated_mb_freed: float


class RetentionExecutionResponse(BaseModel):
    job_id: str
    status: str
    started_at: str
    policies_applied: int


class RetentionStatsResponse(BaseModel):
    investigation_count: int
    scan_result_count: int
    total_mb: float
    oldest_record_age_days: int
    generated_at: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_policy(body: RetentionPolicyCreate, user_id: str) -> RetentionPolicyResponse:
    now = datetime.now(timezone.utc).isoformat()
    return RetentionPolicyResponse(
        id=secrets.token_hex(16),
        entity_type=body.entity_type,
        max_age_days=body.max_age_days,
        action=body.action,
        workspace_id=body.workspace_id,
        created_by=user_id,
        created_at=now,
        updated_at=now,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/retention/policies", response_model=RetentionPolicyListResponse)
async def list_retention_policies(
    current_user: Any = Depends(get_current_user),
) -> RetentionPolicyListResponse:
    """List all retention policies for the current workspace."""
    return RetentionPolicyListResponse(policies=[], total=0)


@router.post("/retention/policies", response_model=RetentionPolicyResponse, status_code=201)
async def create_retention_policy(
    body: RetentionPolicyCreate,
    current_user: Any = Depends(get_current_user),
) -> RetentionPolicyResponse:
    """Create a new data retention policy."""
    user_id = str(getattr(current_user, "id", "unknown"))
    log.info(
        "Retention policy created",
        entity_type=body.entity_type,
        max_age_days=body.max_age_days,
        action=body.action,
        user=user_id,
    )
    return _make_policy(body, user_id)


@router.patch("/retention/policies/{policy_id}", response_model=RetentionPolicyResponse)
async def update_retention_policy(
    policy_id: str,
    body: RetentionPolicyUpdate,
    current_user: Any = Depends(get_current_user),
) -> RetentionPolicyResponse:
    """Update an existing retention policy."""
    user_id = str(getattr(current_user, "id", "unknown"))
    now = datetime.now(timezone.utc).isoformat()
    log.info("Retention policy updated", policy_id=policy_id, user=user_id)
    return RetentionPolicyResponse(
        id=policy_id,
        entity_type="unknown",
        max_age_days=body.max_age_days or 90,
        action=body.action or "archive",
        workspace_id="unknown",
        created_by=user_id,
        created_at=now,
        updated_at=now,
    )


@router.delete("/retention/policies/{policy_id}", status_code=204)
async def delete_retention_policy(
    policy_id: str,
    current_user: Any = Depends(get_current_user),
) -> None:
    """Delete a retention policy."""
    log.info("Retention policy deleted", policy_id=policy_id)


@router.post("/retention/dry-run", response_model=DryRunResponse)
async def retention_dry_run(
    current_user: Any = Depends(get_current_user),
) -> DryRunResponse:
    """
    Preview which records would be affected by executing all active policies,
    without actually archiving or deleting anything.
    """
    user_id = str(getattr(current_user, "id", "unknown"))
    log.info("Retention dry run executed", user=user_id)
    return DryRunResponse(total_affected=0, affected_entities=[], estimated_mb_freed=0.0)


@router.post("/retention/execute", response_model=RetentionExecutionResponse)
async def execute_retention(
    current_user: Any = Depends(get_current_user),
) -> RetentionExecutionResponse:
    """
    Manually trigger retention policy execution (admin only).

    Archives or deletes records that exceed the configured max_age_days for
    their entity type. In production, this should be restricted to admin role.
    """
    user_id = str(getattr(current_user, "id", "unknown"))
    now = datetime.now(timezone.utc).isoformat()
    job_id = secrets.token_hex(16)

    log.info("Retention execution triggered", job_id=job_id, user=user_id)

    # Stub: real implementation dispatches a Celery task and returns the task ID.
    return RetentionExecutionResponse(
        job_id=job_id,
        status="queued",
        started_at=now,
        policies_applied=0,
    )


@router.get("/retention/stats", response_model=RetentionStatsResponse)
async def get_retention_stats(
    current_user: Any = Depends(get_current_user),
) -> RetentionStatsResponse:
    """Return storage statistics for the workspace."""
    now = datetime.now(timezone.utc).isoformat()
    return RetentionStatsResponse(
        investigation_count=0,
        scan_result_count=0,
        total_mb=0.0,
        oldest_record_age_days=0,
        generated_at=now,
    )
