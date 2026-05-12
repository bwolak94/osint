"""Scenario marketplace — browse and clone prebuilt attack scenarios."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.pentest_models import AttackChainModel, PentestScanModel
from src.adapters.scenario_yaml import PREBUILT_SCENARIOS
from src.api.v1.pentesting.dependencies import require_pentester
from src.core.domain.entities.user import User
from src.dependencies import get_db

log = structlog.get_logger(__name__)
router = APIRouter(tags=["scenario-marketplace"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
UserDep = Annotated[User, Depends(require_pentester)]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class MarketplaceScenarioResponse(BaseModel):
    id: str
    name: str
    category: str
    difficulty: str
    description: str
    avg_duration_min: int
    mitre_tactics: list[str]
    steps_count: int


class CloneScenarioResponse(BaseModel):
    chain_id: str
    scan_id: str
    steps_count: int
    message: str


# ---------------------------------------------------------------------------
# GET /marketplace/scenarios
# ---------------------------------------------------------------------------


@router.get("/marketplace/scenarios", response_model=list[MarketplaceScenarioResponse])
async def list_marketplace_scenarios(
    current_user: UserDep,
    category: str | None = Query(default=None, description="Filter by category"),
    difficulty: str | None = Query(default=None, description="easy | medium | hard | expert"),
) -> list[MarketplaceScenarioResponse]:
    """Return all prebuilt scenarios, optionally filtered."""
    results = PREBUILT_SCENARIOS

    if category:
        results = [s for s in results if s["category"] == category]
    if difficulty:
        results = [s for s in results if s["difficulty"] == difficulty]

    return [
        MarketplaceScenarioResponse(
            id=s["id"],
            name=s["name"],
            category=s["category"],
            difficulty=s["difficulty"],
            description=s["description"],
            avg_duration_min=s["avg_duration_min"],
            mitre_tactics=s["mitre_tactics"],
            steps_count=len(s["steps"]),
        )
        for s in results
    ]


# ---------------------------------------------------------------------------
# GET /marketplace/scenarios/{scenario_id}
# ---------------------------------------------------------------------------


@router.get("/marketplace/scenarios/{scenario_id}")
async def get_marketplace_scenario(
    scenario_id: str,
    current_user: UserDep,
) -> dict[str, Any]:
    """Return full details (including steps) for a prebuilt scenario."""
    scenario = next((s for s in PREBUILT_SCENARIOS if s["id"] == scenario_id), None)
    if scenario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found.")
    return scenario


# ---------------------------------------------------------------------------
# POST /marketplace/scenarios/{scenario_id}/clone
# ---------------------------------------------------------------------------


@router.post(
    "/marketplace/scenarios/{scenario_id}/clone",
    response_model=CloneScenarioResponse,
    status_code=status.HTTP_201_CREATED,
)
async def clone_scenario_to_scan(
    scenario_id: str,
    scan_id: uuid.UUID,
    current_user: UserDep,
    db: DbDep,
) -> CloneScenarioResponse:
    """Clone a prebuilt scenario into a scan's attack chains.

    The cloned chain can then be edited in the scenario editor.
    """
    from sqlalchemy import select

    scenario = next((s for s in PREBUILT_SCENARIOS if s["id"] == scenario_id), None)
    if scenario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found.")

    # Verify scan exists
    scan_stmt = select(PentestScanModel).where(PentestScanModel.id == scan_id)
    scan = (await db.execute(scan_stmt)).scalar_one_or_none()
    if scan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found.")

    chain = AttackChainModel(
        id=uuid.uuid4(),
        scan_id=scan_id,
        objective_en=scenario["description"],
        objective_pl=None,
        steps=scenario["steps"],
        overall_likelihood="medium",
        overall_impact="high",
        generated_by=f"marketplace:{scenario_id}",
        created_at=_utcnow(),
    )
    db.add(chain)
    await db.commit()

    await log.ainfo(
        "marketplace_scenario_cloned",
        scenario_id=scenario_id,
        scan_id=str(scan_id),
        chain_id=str(chain.id),
        user_id=str(current_user.id),
    )

    return CloneScenarioResponse(
        chain_id=str(chain.id),
        scan_id=str(scan_id),
        steps_count=len(scenario["steps"]),
        message=f"Cloned '{scenario['name']}' to scan {scan_id}.",
    )
