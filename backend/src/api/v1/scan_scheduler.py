"""Scan scheduler — schedule recurring OSINT scans on a cron-like schedule.

POST /api/v1/scan-scheduler/jobs — create a scheduled scan job
GET  /api/v1/scan-scheduler/jobs — list scheduled jobs
DELETE /api/v1/scan-scheduler/jobs/{job_id} — delete a scheduled job
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.auth.dependencies import get_current_user
from src.adapters.db.database import get_db
from src.adapters.db.models import UserModel

log = structlog.get_logger(__name__)

router = APIRouter()

# In-memory store (replace with DB model for production persistence)
_SCHEDULED_JOBS: dict[str, dict[str, Any]] = {}

_VALID_INTERVALS = {
    "hourly": 3600,
    "daily": 86400,
    "weekly": 604800,
    "monthly": 2592000,
}


class ScheduleJobRequest(BaseModel):
    investigation_id: str
    target: str
    scanners: list[str]
    interval: str  # hourly | daily | weekly | monthly
    notify_on_change: bool = True
    description: str | None = None


class ScheduledJob(BaseModel):
    job_id: str
    investigation_id: str
    target: str
    scanners: list[str]
    interval: str
    interval_seconds: int
    next_run: str
    created_at: str
    notify_on_change: bool
    is_active: bool
    description: str | None
    owner_id: str


@router.post("/scan-scheduler/jobs", response_model=ScheduledJob,
             status_code=status.HTTP_201_CREATED, tags=["scan-scheduler"])
async def create_scheduled_job(
    req: ScheduleJobRequest,
    current_user: UserModel = Depends(get_current_user),
) -> ScheduledJob:
    """Create a recurring scan schedule for an investigation."""
    if req.interval not in _VALID_INTERVALS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid interval '{req.interval}'. Valid: {', '.join(_VALID_INTERVALS)}",
        )

    # Limit to 10 jobs per user
    user_jobs = [j for j in _SCHEDULED_JOBS.values() if j["owner_id"] == str(current_user.id)]
    if len(user_jobs) >= 10:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Maximum 10 scheduled scan jobs per user",
        )

    job_id = str(uuid4())
    now = datetime.now(timezone.utc)
    interval_secs = _VALID_INTERVALS[req.interval]
    next_run = datetime.fromtimestamp(now.timestamp() + interval_secs, tz=timezone.utc)

    job = {
        "job_id": job_id,
        "investigation_id": req.investigation_id,
        "target": req.target,
        "scanners": req.scanners,
        "interval": req.interval,
        "interval_seconds": interval_secs,
        "next_run": next_run.isoformat(),
        "created_at": now.isoformat(),
        "notify_on_change": req.notify_on_change,
        "is_active": True,
        "description": req.description,
        "owner_id": str(current_user.id),
    }
    _SCHEDULED_JOBS[job_id] = job

    log.info("Scheduled scan job created", job_id=job_id, target=req.target,
             interval=req.interval, user_id=str(current_user.id))

    return ScheduledJob(**job)


@router.get("/scan-scheduler/jobs", response_model=list[ScheduledJob],
            tags=["scan-scheduler"])
async def list_scheduled_jobs(
    current_user: UserModel = Depends(get_current_user),
) -> list[ScheduledJob]:
    """List all scheduled scan jobs for the current user."""
    user_jobs = [
        ScheduledJob(**j) for j in _SCHEDULED_JOBS.values()
        if j["owner_id"] == str(current_user.id)
    ]
    return sorted(user_jobs, key=lambda j: j.created_at, reverse=True)


@router.delete("/scan-scheduler/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT,
               tags=["scan-scheduler"])
async def delete_scheduled_job(
    job_id: str,
    current_user: UserModel = Depends(get_current_user),
) -> None:
    """Delete a scheduled scan job."""
    job = _SCHEDULED_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job["owner_id"] != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your job")
    del _SCHEDULED_JOBS[job_id]


@router.patch("/scan-scheduler/jobs/{job_id}/toggle", response_model=ScheduledJob,
              tags=["scan-scheduler"])
async def toggle_scheduled_job(
    job_id: str,
    current_user: UserModel = Depends(get_current_user),
) -> ScheduledJob:
    """Toggle a scheduled job between active and paused."""
    job = _SCHEDULED_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job["owner_id"] != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your job")
    job["is_active"] = not job["is_active"]
    return ScheduledJob(**job)
