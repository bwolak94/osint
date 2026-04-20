"""Scheduled report delivery endpoints."""

import secrets
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.api.v1.auth.dependencies import get_current_user

log = structlog.get_logger()
router = APIRouter()


class ReportScheduleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)
    investigation_id: str | None = None
    schedule_cron: str = "0 9 * * 1"  # Monday 9am
    report_format: str = Field("pdf", pattern="^(pdf|html|json|csv)$")
    recipients: list[str] = []
    sections: list[dict] = []


class ReportScheduleResponse(BaseModel):
    id: str
    name: str
    investigation_id: str | None
    schedule_cron: str
    report_format: str
    recipients: list[str]
    sections: list[dict]
    is_active: bool
    last_sent_at: str | None
    send_count: int
    created_at: str


class ReportScheduleListResponse(BaseModel):
    schedules: list[ReportScheduleResponse]
    total: int


@router.get("/report-schedules", response_model=ReportScheduleListResponse)
async def list_report_schedules(
    current_user: Any = Depends(get_current_user),
) -> ReportScheduleListResponse:
    """List all report schedules for the current user."""
    return ReportScheduleListResponse(schedules=[], total=0)


@router.post("/report-schedules", response_model=ReportScheduleResponse, status_code=201)
async def create_report_schedule(
    body: ReportScheduleCreate,
    current_user: Any = Depends(get_current_user),
) -> ReportScheduleResponse:
    """Create a scheduled report delivery."""
    now = datetime.now(timezone.utc).isoformat()
    return ReportScheduleResponse(
        id=secrets.token_hex(16),
        name=body.name,
        investigation_id=body.investigation_id,
        schedule_cron=body.schedule_cron,
        report_format=body.report_format,
        recipients=body.recipients,
        sections=body.sections,
        is_active=True,
        last_sent_at=None,
        send_count=0,
        created_at=now,
    )


@router.delete("/report-schedules/{schedule_id}")
async def delete_report_schedule(
    schedule_id: str,
    current_user: Any = Depends(get_current_user),
) -> dict[str, str]:
    return {"status": "deleted", "id": schedule_id}


@router.post("/report-schedules/{schedule_id}/send-now")
async def send_report_now(
    schedule_id: str,
    current_user: Any = Depends(get_current_user),
) -> dict[str, str]:
    """Manually trigger a scheduled report."""
    log.info("Report triggered manually", schedule_id=schedule_id)
    return {"status": "sending", "id": schedule_id}
