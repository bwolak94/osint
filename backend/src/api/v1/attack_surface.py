"""Live Attack Surface Monitor — asset discovery with delta alerts."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Annotated
from uuid import uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User

log = structlog.get_logger()
router = APIRouter()

# ---------------------------------------------------------------------------
# In-memory store (replace with DB model in production)
# ---------------------------------------------------------------------------

_SUBSCRIPTIONS: dict[str, dict[str, Any]] = {}
_SNAPSHOTS: dict[str, list[dict[str, Any]]] = {}  # sub_id → last snapshot assets


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class AssetSeed(BaseModel):
    type: str = Field(..., pattern="^(domain|ip_cidr|asn|org)$")
    value: str = Field(..., min_length=1)


class CreateSubscriptionRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    seeds: list[AssetSeed] = Field(..., min_length=1)
    scan_interval_hours: int = Field(24, ge=1, le=168)
    alert_on: list[str] = Field(
        default_factory=lambda: ["new_asset", "port_change", "vuln_detected"],
    )


class AssetRecord(BaseModel):
    asset_id: str
    type: str  # ip, domain, subdomain, port, cert
    value: str
    first_seen: str
    last_seen: str
    tags: list[str]
    risk_score: float


class DeltaAlert(BaseModel):
    alert_id: str
    subscription_id: str
    type: str  # new_asset | asset_removed | port_change | vuln_detected
    asset: AssetRecord
    previous_value: str | None
    detected_at: str


class SubscriptionResponse(BaseModel):
    id: str
    name: str
    seeds: list[dict[str, str]]
    scan_interval_hours: int
    alert_on: list[str]
    last_scan_at: str | None
    asset_count: int
    created_at: str
    status: str


class SubscriptionDetail(SubscriptionResponse):
    assets: list[AssetRecord]
    recent_alerts: list[DeltaAlert]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _asset_hash(asset_type: str, value: str) -> str:
    return hashlib.sha256(f"{asset_type}:{value}".encode()).hexdigest()[:16]


def _simulate_discovery(seeds: list[dict[str, Any]]) -> list[AssetRecord]:
    """Produce synthetic asset records from seeds (replaced by real scanners in prod)."""
    now = datetime.now(timezone.utc).isoformat()
    assets: list[AssetRecord] = []
    for seed in seeds:
        if seed["type"] == "domain":
            domain = seed["value"]
            assets += [
                AssetRecord(
                    asset_id=_asset_hash("ip", f"1.2.3.{i}"),
                    type="ip", value=f"1.2.3.{i}",
                    first_seen=now, last_seen=now,
                    tags=["resolved"], risk_score=0.1 * i,
                )
                for i in range(1, 4)
            ]
            assets.append(AssetRecord(
                asset_id=_asset_hash("subdomain", f"mail.{domain}"),
                type="subdomain", value=f"mail.{domain}",
                first_seen=now, last_seen=now,
                tags=["mail"], risk_score=0.2,
            ))
        elif seed["type"] == "ip_cidr":
            assets.append(AssetRecord(
                asset_id=_asset_hash("port", f"{seed['value']}:443"),
                type="port", value=f"{seed['value']}:443",
                first_seen=now, last_seen=now,
                tags=["https"], risk_score=0.05,
            ))
    return assets


def _compute_deltas(
    old: list[dict[str, Any]],
    new_assets: list[AssetRecord],
    sub_id: str,
) -> list[DeltaAlert]:
    old_ids = {a["asset_id"] for a in old}
    now = datetime.now(timezone.utc).isoformat()
    alerts: list[DeltaAlert] = []
    for asset in new_assets:
        if asset.asset_id not in old_ids:
            alerts.append(DeltaAlert(
                alert_id=str(uuid4()),
                subscription_id=sub_id,
                type="new_asset",
                asset=asset,
                previous_value=None,
                detected_at=now,
            ))
    return alerts


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/attack-surface/subscriptions", response_model=SubscriptionResponse, status_code=201)
async def create_subscription(
    body: CreateSubscriptionRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> SubscriptionResponse:
    """Create an attack surface monitoring subscription."""
    sub_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    seeds_dicts = [s.model_dump() for s in body.seeds]
    _SUBSCRIPTIONS[sub_id] = {
        "id": sub_id,
        "user_id": str(current_user.id),
        "name": body.name,
        "seeds": seeds_dicts,
        "scan_interval_hours": body.scan_interval_hours,
        "alert_on": body.alert_on,
        "last_scan_at": None,
        "asset_count": 0,
        "created_at": now,
        "status": "active",
    }
    _SNAPSHOTS[sub_id] = []
    log.info("Attack surface subscription created", id=sub_id, name=body.name)
    return SubscriptionResponse(**_SUBSCRIPTIONS[sub_id])


@router.get("/attack-surface/subscriptions", response_model=list[SubscriptionResponse])
async def list_subscriptions(
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[SubscriptionResponse]:
    return [
        SubscriptionResponse(**s)
        for s in _SUBSCRIPTIONS.values()
        if s["user_id"] == str(current_user.id)
    ]


@router.get("/attack-surface/subscriptions/{sub_id}", response_model=SubscriptionDetail)
async def get_subscription(
    sub_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> SubscriptionDetail:
    sub = _SUBSCRIPTIONS.get(sub_id)
    if not sub or sub["user_id"] != str(current_user.id):
        raise HTTPException(404, "Subscription not found")

    assets = _simulate_discovery(sub["seeds"])
    deltas = _compute_deltas(_SNAPSHOTS.get(sub_id, []), assets, sub_id)

    return SubscriptionDetail(
        **sub,
        asset_count=len(assets),
        assets=assets,
        recent_alerts=deltas[:20],
    )


@router.post("/attack-surface/subscriptions/{sub_id}/scan", response_model=dict[str, Any])
async def trigger_scan(
    sub_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Trigger an immediate scan for an attack surface subscription."""
    sub = _SUBSCRIPTIONS.get(sub_id)
    if not sub or sub["user_id"] != str(current_user.id):
        raise HTTPException(404, "Subscription not found")

    assets = _simulate_discovery(sub["seeds"])
    deltas = _compute_deltas(_SNAPSHOTS.get(sub_id, []), assets, sub_id)

    # Update snapshot
    _SNAPSHOTS[sub_id] = [a.model_dump() for a in assets]
    now = datetime.now(timezone.utc).isoformat()
    sub["last_scan_at"] = now
    sub["asset_count"] = len(assets)

    log.info("Attack surface scan triggered", sub_id=sub_id, assets=len(assets), deltas=len(deltas))
    return {
        "sub_id": sub_id,
        "assets_discovered": len(assets),
        "new_alerts": len(deltas),
        "scanned_at": now,
    }


@router.delete("/attack-surface/subscriptions/{sub_id}", status_code=204, response_class=Response)
async def delete_subscription(
    sub_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    sub = _SUBSCRIPTIONS.get(sub_id)
    if not sub or sub["user_id"] != str(current_user.id):
        raise HTTPException(404, "Subscription not found")
    _SUBSCRIPTIONS.pop(sub_id, None)
    return Response(status_code=204)
    _SNAPSHOTS.pop(sub_id, None)
