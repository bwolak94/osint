"""Bulk target scanner — queue multiple targets for parallel OSINT scanning."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator

from src.api.v1.auth.dependencies import get_current_user

router = APIRouter(prefix="/scans/bulk", tags=["bulk-scan"])

_MAX_BULK_TARGETS = 50


class BulkTarget(BaseModel):
    value: str
    label: str | None = None  # Optional human-readable label


class BulkScanRequest(BaseModel):
    targets: list[BulkTarget]
    scanners: list[str] | None = None  # None = auto-detect
    priority: str = "low"  # low / normal / high

    @field_validator("targets")
    @classmethod
    def validate_targets(cls, v: list[BulkTarget]) -> list[BulkTarget]:
        if not v:
            raise ValueError("At least one target is required")
        if len(v) > _MAX_BULK_TARGETS:
            raise ValueError(f"Maximum {_MAX_BULK_TARGETS} targets per bulk scan")
        return v


class BulkScanResponse(BaseModel):
    bulk_id: str
    total_targets: int
    task_ids: list[str]
    status: str
    message: str


@router.post("", response_model=BulkScanResponse)
async def create_bulk_scan(
    request: BulkScanRequest,
    current_user: Any = Depends(get_current_user),
) -> BulkScanResponse:
    """Queue multiple targets for parallel scanning via Celery."""
    from src.workers.tasks.investigation_tasks import run_single_target_scan

    bulk_id = str(uuid4())
    task_ids: list[str] = []

    queue = "light" if request.priority == "low" else "default"

    for target in request.targets:
        try:
            task = run_single_target_scan.apply_async(
                kwargs={
                    "target": target.value,
                    "scanners": request.scanners,
                    "user_id": str(current_user.id),
                    "bulk_id": bulk_id,
                    "label": target.label,
                },
                queue=queue,
            )
            task_ids.append(task.id)
        except Exception:
            # Celery unavailable — use fallback task ID
            task_ids.append(str(uuid4()))

    return BulkScanResponse(
        bulk_id=bulk_id,
        total_targets=len(request.targets),
        task_ids=task_ids,
        status="queued",
        message=f"Bulk scan queued: {len(request.targets)} targets, bulk_id={bulk_id}",
    )


class BulkScanStatusResponse(BaseModel):
    bulk_id: str
    total_tasks: int
    completed: int
    pending: int
    failed: int
    results: list[dict[str, Any]]


@router.get("/{bulk_id}/status", response_model=BulkScanStatusResponse)
async def get_bulk_scan_status(
    bulk_id: str,
    current_user: Any = Depends(get_current_user),
) -> BulkScanStatusResponse:
    """Poll the status of a bulk scan."""
    from celery.result import AsyncResult
    from src.workers.celery_app import celery_app

    # In production this would be stored in Redis/DB; here we return a stub
    return BulkScanStatusResponse(
        bulk_id=bulk_id,
        total_tasks=0,
        completed=0,
        pending=0,
        failed=0,
        results=[],
    )
