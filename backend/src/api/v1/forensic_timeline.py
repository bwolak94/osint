"""Forensic Timeline Reconstruction — auto-generate a chronological event timeline from all evidence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Annotated
from uuid import uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User
from src.dependencies import get_db

log = structlog.get_logger()
router = APIRouter()

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TimelineEvent(BaseModel):
    event_id: str
    timestamp: str
    event_type: str  # scan_result | comment | status_change | entity_created | external_event
    actor: str       # scanner name, user, or "system"
    summary: str
    detail: dict[str, Any]
    entity_type: str | None  # ip | domain | email | person | ...
    entity_value: str | None
    confidence: float
    source: str      # scanner name or user-provided
    tags: list[str]


class SwimLane(BaseModel):
    lane_id: str
    label: str  # e.g. "Email Events", "Network Events", "User Actions"
    events: list[TimelineEvent]
    color: str


class ForensicTimelineResponse(BaseModel):
    investigation_id: str
    total_events: int
    time_range: dict[str, str | None]  # {start, end}
    lanes: list[SwimLane]
    generated_at: str


# ---------------------------------------------------------------------------
# Lane classification
# ---------------------------------------------------------------------------

_LANE_CONFIG: list[dict[str, Any]] = [
    {"id": "network", "label": "Network", "color": "var(--info-500)", "scanners": {"shodan", "geoip", "asn", "dns_lookup", "cert_transparency"}},
    {"id": "email", "label": "Email & Identity", "color": "var(--success-500)", "scanners": {"holehe", "hibp", "hunter"}},
    {"id": "web", "label": "Web & Domain", "color": "var(--brand-400)", "scanners": {"whois", "virustotal", "playwright_krs", "playwright_ceidg"}},
    {"id": "social", "label": "Social", "color": "var(--warning-500)", "scanners": {"github", "telegram", "twitter", "tiktok"}},
    {"id": "system", "label": "System Events", "color": "var(--text-tertiary)", "scanners": set()},
]


def _classify_lane(scanner: str) -> str:
    for lane in _LANE_CONFIG:
        if scanner in lane["scanners"]:
            return lane["id"]
    return "system"


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.get("/investigations/{investigation_id}/forensic-timeline", response_model=ForensicTimelineResponse)
async def get_forensic_timeline(
    investigation_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(500, ge=1, le=2000),
) -> ForensicTimelineResponse:
    """
    Reconstruct a forensic timeline from all scan results, comments, and status changes
    for an investigation. Events are organised into swim-lanes by source category.
    """
    from src.adapters.db.models import InvestigationModel, ScanResultModel

    # Verify investigation access
    result = await db.execute(
        select(InvestigationModel).where(
            InvestigationModel.id == investigation_id,
            InvestigationModel.owner_id == current_user.id,
        )
    )
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(404, "Investigation not found")

    # Fetch scan results
    sr_result = await db.execute(
        select(ScanResultModel)
        .where(ScanResultModel.investigation_id == investigation_id)
        .order_by(ScanResultModel.created_at)
        .limit(limit)
    )
    scan_results = sr_result.scalars().all()

    events_by_lane: dict[str, list[TimelineEvent]] = {lane["id"]: [] for lane in _LANE_CONFIG}

    for sr in scan_results:
        raw: dict[str, Any] = sr.raw_data if isinstance(sr.raw_data, dict) else {}
        scanner_name = sr.scanner_name or "unknown"
        lane_id = _classify_lane(scanner_name)

        # Extract any embedded timestamps from raw data
        event_time = sr.created_at.isoformat() if sr.created_at else datetime.now(timezone.utc).isoformat()
        for ts_key in ("date", "timestamp", "created_at", "first_seen", "last_seen"):
            if ts_key in raw and isinstance(raw[ts_key], str):
                event_time = raw[ts_key]
                break

        event = TimelineEvent(
            event_id=str(sr.id),
            timestamp=event_time,
            event_type="scan_result",
            actor=scanner_name,
            summary=f"{scanner_name}: {len(sr.raw_data.get("nodes", sr.raw_data.get("results", []))) if isinstance(sr.raw_data, dict) else 0} finding(s) for {sr.input_value or ''}",
            detail={
                "findings_count": len(sr.raw_data.get("nodes", sr.raw_data.get("results", []))) if isinstance(sr.raw_data, dict) else 0,
                "duration_ms": sr.duration_ms,
                "status": sr.status,
                "input_value": sr.input_value,
            },
            entity_type=getattr(sr, "input_type", None),
            entity_value=sr.input_value,
            confidence=float(getattr(sr, "confidence", 0.5)),
            source=scanner_name,
            tags=[sr.status or "unknown"] if sr.status else [],
        )
        events_by_lane[lane_id].append(event)

    # Add investigation lifecycle event
    created_event = TimelineEvent(
        event_id=f"inv-created-{investigation_id}",
        timestamp=inv.created_at.isoformat() if inv.created_at else "",
        event_type="status_change",
        actor="system",
        summary=f"Investigation created: {inv.title}",
        detail={"status": "draft", "title": inv.title},
        entity_type=None, entity_value=None,
        confidence=1.0, source="system", tags=["lifecycle"],
    )
    events_by_lane["system"].append(created_event)

    # Build lanes
    all_timestamps: list[str] = []
    lanes: list[SwimLane] = []
    for lane_cfg in _LANE_CONFIG:
        lane_events = sorted(events_by_lane[lane_cfg["id"]], key=lambda e: e.timestamp)
        all_timestamps.extend(e.timestamp for e in lane_events)
        lanes.append(SwimLane(
            lane_id=lane_cfg["id"],
            label=lane_cfg["label"],
            events=lane_events,
            color=lane_cfg["color"],
        ))

    time_range = {
        "start": min(all_timestamps) if all_timestamps else None,
        "end": max(all_timestamps) if all_timestamps else None,
    }

    total = sum(len(l.events) for l in lanes)
    log.info("Forensic timeline built", investigation_id=investigation_id, total_events=total)

    return ForensicTimelineResponse(
        investigation_id=investigation_id,
        total_events=total,
        time_range=time_range,
        lanes=lanes,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
