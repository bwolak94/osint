"""Timeline anomaly detection for investigations."""

from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.database import get_db
from src.adapters.db.models import InvestigationModel, ScanResultModel, UserModel
from src.api.v1.auth.dependencies import get_current_user

log = structlog.get_logger(__name__)

router = APIRouter()

_DATE_FIELDS = ("date", "created_at", "timestamp", "filed", "first_seen", "last_seen")


def _try_parse(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str):
        value = str(value)
    try:
        from dateutil import parser as dtparser
        dt = dtparser.parse(value)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            dt = datetime.strptime(value[:len(fmt)], fmt)
            return dt.replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return None


def _extract_timestamps(scan_results: list[ScanResultModel]) -> list[datetime]:
    timestamps: list[datetime] = []
    now = datetime.now(timezone.utc)

    for sr in scan_results:
        if sr.created_at:
            dt = _try_parse(sr.created_at)
            if dt:
                timestamps.append(dt)

        findings = sr.findings or {}
        if isinstance(findings, dict):
            items_to_check: list[dict] = [findings]
            # Also look inside nested lists
            for v in findings.values():
                if isinstance(v, list):
                    items_to_check.extend(item for item in v if isinstance(item, dict))
        elif isinstance(findings, list):
            items_to_check = [item for item in findings if isinstance(item, dict)]
        else:
            items_to_check = []

        for item in items_to_check:
            for field in _DATE_FIELDS:
                raw = item.get(field)
                if raw:
                    dt = _try_parse(raw)
                    if dt:
                        timestamps.append(dt)

    return sorted(timestamps)


class TimelineAnomaly(BaseModel):
    anomaly_type: str
    timestamp: str
    description: str
    severity: str  # high/medium/low


class TimelineAnomalyResponse(BaseModel):
    investigation_id: str
    total_events: int
    anomalies: list[TimelineAnomaly]
    first_event: str | None
    last_event: str | None
    timeline_span_days: float


@router.get(
    "/investigations/{investigation_id}/timeline-anomalies",
    response_model=TimelineAnomalyResponse,
    tags=["timeline-anomaly"],
)
async def get_timeline_anomalies(
    investigation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> TimelineAnomalyResponse:
    """Detect temporal anomalies in investigation scan result timestamps."""
    # Verify investigation exists and belongs to user
    inv_result = await db.execute(
        select(InvestigationModel).where(InvestigationModel.id == investigation_id)
    )
    investigation = inv_result.scalar_one_or_none()
    if investigation is None:
        raise HTTPException(status_code=404, detail="Investigation not found")

    # Fetch scan results (limit 200)
    result = await db.execute(
        select(ScanResultModel)
        .where(ScanResultModel.investigation_id == investigation_id)
        .limit(200)
    )
    scan_results = list(result.scalars().all())

    timestamps = _extract_timestamps(scan_results)
    now = datetime.now(timezone.utc)
    anomalies: list[TimelineAnomaly] = []

    # Future date anomaly
    for ts in timestamps:
        if ts > now:
            anomalies.append(
                TimelineAnomaly(
                    anomaly_type="future_date",
                    timestamp=ts.isoformat(),
                    description=f"Event dated in the future: {ts.isoformat()}",
                    severity="high",
                )
            )

    # Gap and burst anomalies (work on sorted timestamps)
    valid = [ts for ts in timestamps if ts <= now]

    for i in range(1, len(valid)):
        delta = valid[i] - valid[i - 1]
        delta_days = delta.total_seconds() / 86400

        # Gap anomaly: > 30 days between consecutive events
        if delta_days > 30:
            anomalies.append(
                TimelineAnomaly(
                    anomaly_type="temporal_gap",
                    timestamp=valid[i].isoformat(),
                    description=(
                        f"Gap of {delta_days:.1f} days between events "
                        f"({valid[i - 1].isoformat()} → {valid[i].isoformat()})"
                    ),
                    severity="medium",
                )
            )

    # Burst anomaly: 5+ events within any 1-hour window
    hour_seconds = 3600
    for i in range(len(valid)):
        window = [
            ts
            for ts in valid[i:]
            if (ts - valid[i]).total_seconds() <= hour_seconds
        ]
        if len(window) >= 5:
            anomalies.append(
                TimelineAnomaly(
                    anomaly_type="activity_burst",
                    timestamp=valid[i].isoformat(),
                    description=(
                        f"{len(window)} events within 1 hour starting at {valid[i].isoformat()}"
                    ),
                    severity="medium",
                )
            )
            # Skip to end of window to avoid duplicate burst reports
            break

    # Off-hours anomaly: events between 00:00-05:00 UTC
    for ts in valid:
        if 0 <= ts.hour < 5:
            anomalies.append(
                TimelineAnomaly(
                    anomaly_type="off_hours_activity",
                    timestamp=ts.isoformat(),
                    description=f"Activity at off-hours UTC time: {ts.strftime('%H:%M')}",
                    severity="low",
                )
            )

    first_event = valid[0].isoformat() if valid else None
    last_event = valid[-1].isoformat() if valid else None
    span_days = 0.0
    if len(valid) >= 2:
        span_days = round((valid[-1] - valid[0]).total_seconds() / 86400, 2)

    log.info(
        "timeline_anomalies_computed",
        investigation_id=investigation_id,
        total_events=len(timestamps),
        anomaly_count=len(anomalies),
    )

    return TimelineAnomalyResponse(
        investigation_id=investigation_id,
        total_events=len(timestamps),
        anomalies=anomalies,
        first_event=first_event,
        last_event=last_event,
        timeline_span_days=span_days,
    )
