"""Breach & Attack Simulation (BAS) API.

Provides a catalog of pre-built attack playbooks mapped to real threat actors
and MITRE ATT&CK techniques. Each scenario is a named set of tool modules
that can be launched as a PentestScan.

Endpoints:
  GET  /bas/scenarios          — list all available BAS scenarios
  POST /bas/run                — execute a BAS scenario
  GET  /bas/runs               — list previous BAS scenario runs
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from src.adapters.db.pentest_models import EngagementModel, PentestScanModel, TargetModel
from src.api.v1.auth.dependencies import get_current_user
from src.api.v1.pentesting.dependencies import require_pentester
from src.core.domain.entities.user import User
from src.dependencies import get_db

log = structlog.get_logger(__name__)

router = APIRouter(tags=["bas"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
UserDep = Annotated[User, Depends(require_pentester)]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# BAS Scenario Catalog
# ---------------------------------------------------------------------------

BAS_SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "apt28-recon",
        "name": "APT28 Recon Phase",
        "threat_actor": "APT28 (Fancy Bear)",
        "ttps": ["T1595", "T1590"],
        "modules": ["subfinder", "httpx", "nmap"],
        "description": "Recon techniques attributed to APT28",
    },
    {
        "id": "ransomware-sim",
        "name": "Ransomware Simulation",
        "threat_actor": "Generic Ransomware",
        "ttps": ["T1486", "T1490"],
        "modules": ["nmap", "nuclei", "spray"],
        "description": "Safe ransomware behavior simulation",
    },
    {
        "id": "web-compromise",
        "name": "Web Application Compromise",
        "threat_actor": "Generic",
        "ttps": ["T1190", "T1505.003"],
        "modules": ["httpx", "nuclei", "ffuf", "sqlmap"],
        "description": "Full web app attack chain",
    },
    {
        "id": "credential-theft",
        "name": "Credential Theft Campaign",
        "threat_actor": "Generic",
        "ttps": ["T1110.003", "T1558.003"],
        "modules": ["spray", "kerberoast"],
        "description": "Credential spraying and Kerberoasting",
    },
    {
        "id": "ad-domination",
        "name": "AD Full Compromise Path",
        "threat_actor": "Lazarus Group",
        "ttps": ["T1558.003", "T1558.004", "T1003.001"],
        "modules": ["kerberoast", "asreproast"],
        "description": "AD escalation to Domain Admin",
    },
    {
        "id": "exfil-test",
        "name": "Data Exfiltration Test",
        "threat_actor": "Generic",
        "ttps": ["T1048", "T1567"],
        "modules": ["nuclei", "httpx"],
        "description": "Test DLP controls via HTTP/DNS exfil simulation",
    },
    {
        "id": "cloud-exposure",
        "name": "Cloud Misconfiguration",
        "threat_actor": "Generic",
        "ttps": ["T1530", "T1537"],
        "modules": ["nuclei", "httpx"],
        "description": "Cloud storage and metadata exposure",
    },
    {
        "id": "phishing-landing",
        "name": "Phishing Landing Page Test",
        "threat_actor": "Generic",
        "ttps": ["T1566.002"],
        "modules": ["httpx"],
        "description": "Test email gateway and landing page detection",
    },
    {
        "id": "lotl-detection",
        "name": "Living-off-the-Land Detection",
        "threat_actor": "Generic",
        "ttps": ["T1218", "T1059.003"],
        "modules": ["nuclei"],
        "description": "Test EDR detection of LoTL techniques",
    },
    {
        "id": "supply-chain-sim",
        "name": "Supply Chain Attack Simulation",
        "threat_actor": "SolarWinds-style",
        "ttps": ["T1195", "T1078"],
        "modules": ["subfinder", "nuclei"],
        "description": "Software supply chain attack vectors",
    },
]

# Index for fast lookup by id
_SCENARIO_BY_ID: dict[str, dict[str, Any]] = {s["id"]: s for s in BAS_SCENARIOS}


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ScenarioResponse(BaseModel):
    id: str
    name: str
    threat_actor: str
    ttps: list[str]
    modules: list[str]
    description: str


class RunBASRequest(BaseModel):
    scenario_id: str
    engagement_id: uuid.UUID
    target: str


class BASRunResponse(BaseModel):
    scan_id: uuid.UUID
    scenario_id: str
    scenario_name: str
    engagement_id: uuid.UUID
    target: str
    modules: list[str]
    status: str
    celery_task_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ScanSummaryResponse(BaseModel):
    id: uuid.UUID
    engagement_id: uuid.UUID
    target_id: uuid.UUID
    user_id: uuid.UUID
    profile: str
    selected_modules: list[str] | None
    status: str
    progress_pct: int
    celery_task_id: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class BASRunSummaryResponse(ScanSummaryResponse):
    """Extended summary that includes human-readable scenario name and target value."""

    scenario_name: str = ""
    target: str = ""


# ---------------------------------------------------------------------------
# GET /bas/scenarios
# ---------------------------------------------------------------------------


@router.get("/scenarios", response_model=list[ScenarioResponse])
async def list_scenarios(
    current_user: UserDep,
) -> list[ScenarioResponse]:
    """Return the full BAS scenario catalog."""
    return [ScenarioResponse(**s) for s in BAS_SCENARIOS]


# ---------------------------------------------------------------------------
# POST /bas/run
# ---------------------------------------------------------------------------


@router.post("/run", status_code=status.HTTP_201_CREATED, response_model=BASRunResponse)
async def run_bas_scenario(
    request: RunBASRequest,
    current_user: UserDep,
    db: DbDep,
) -> BASRunResponse:
    """Launch a BAS scenario.

    Creates a PentestScan with the scenario's modules as selected_modules,
    creates or reuses a target entry for the supplied target string, and
    enqueues the Celery orchestrator.
    """
    scenario = _SCENARIO_BY_ID.get(request.scenario_id)
    if scenario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"BAS scenario '{request.scenario_id}' not found. "
            f"Available: {list(_SCENARIO_BY_ID.keys())}",
        )

    # Validate engagement exists and is active
    eng_stmt = select(EngagementModel).where(EngagementModel.id == request.engagement_id)
    engagement = (await db.execute(eng_stmt)).scalar_one_or_none()
    if engagement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Engagement not found."
        )
    if engagement.status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Engagement is not active (status: {engagement.status}).",
        )

    now = _utcnow()
    if engagement.expires_at and engagement.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Engagement has expired."
        )

    # Find or create a Target entry for the given target string
    target_type = _infer_target_type(request.target)
    tgt_stmt = select(TargetModel).where(
        TargetModel.engagement_id == request.engagement_id,
        TargetModel.value == request.target,
    )
    target_model = (await db.execute(tgt_stmt)).scalar_one_or_none()

    if target_model is None:
        target_model = TargetModel(
            id=uuid.uuid4(),
            engagement_id=request.engagement_id,
            type=target_type,
            value=request.target,
            metadata_={
                "source": "bas",
                "scenario_id": request.scenario_id,
            },
        )
        db.add(target_model)
        await db.flush()

    # Create the PentestScan
    scan = PentestScanModel(
        id=uuid.uuid4(),
        engagement_id=request.engagement_id,
        user_id=current_user.id,
        target_id=target_model.id,
        profile="bas",
        selected_modules=scenario["modules"],
        status="queued",
        celery_task_id=None,
        progress_pct=0,
        created_at=now,
    )
    db.add(scan)
    await db.flush()

    # Enqueue the Celery orchestrator task
    celery_task_id: str | None = None
    try:
        from src.workers.pentest_orchestrator import orchestrate_scan

        task = orchestrate_scan.apply_async(
            args=[str(scan.id)],
            queue="pentest_heavy",
        )
        celery_task_id = task.id
        scan.celery_task_id = celery_task_id
        await db.flush()
    except Exception as exc:
        await log.awarn(
            "bas_celery_enqueue_failed",
            scan_id=str(scan.id),
            scenario_id=request.scenario_id,
            error=str(exc),
        )
        scan.celery_task_id = f"pending:{scan.id}"
        celery_task_id = scan.celery_task_id
        await db.flush()

    await log.ainfo(
        "bas_run_created",
        scenario_id=request.scenario_id,
        scan_id=str(scan.id),
        modules=scenario["modules"],
        user_id=str(current_user.id),
    )

    return BASRunResponse(
        scan_id=scan.id,
        scenario_id=request.scenario_id,
        scenario_name=scenario["name"],
        engagement_id=scan.engagement_id,
        target=request.target,
        modules=scenario["modules"],
        status=scan.status,
        celery_task_id=celery_task_id,
        created_at=scan.created_at,
    )


# ---------------------------------------------------------------------------
# GET /bas/runs
# ---------------------------------------------------------------------------


@router.get("/runs", response_model=list[BASRunSummaryResponse])
async def list_bas_runs(
    current_user: UserDep,
    db: DbDep,
    engagement_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[BASRunSummaryResponse]:
    """List previous BAS runs (scans with profile='bas') for the current user."""
    TargetAlias = aliased(TargetModel)
    stmt = (
        select(PentestScanModel, TargetAlias)
        .outerjoin(TargetAlias, PentestScanModel.target_id == TargetAlias.id)
        .where(
            PentestScanModel.user_id == current_user.id,
            PentestScanModel.profile == "bas",
        )
        .order_by(PentestScanModel.created_at.desc())
        .limit(limit)
    )
    if engagement_id is not None:
        stmt = stmt.where(PentestScanModel.engagement_id == engagement_id)

    rows = (await db.execute(stmt)).all()
    result: list[BASRunSummaryResponse] = []
    for scan, target in rows:
        target_value = target.value if target else ""
        if target and target.metadata_:
            scenario_id = target.metadata_.get("scenario_id", "")
            scenario_entry = _SCENARIO_BY_ID.get(scenario_id)
            scenario_name = scenario_entry["name"] if scenario_entry else scan.profile
        else:
            scenario_name = scan.profile
        result.append(
            BASRunSummaryResponse(
                id=scan.id,
                engagement_id=scan.engagement_id,
                target_id=scan.target_id,
                user_id=scan.user_id,
                profile=scan.profile,
                selected_modules=scan.selected_modules,
                status=scan.status,
                progress_pct=scan.progress_pct,
                celery_task_id=scan.celery_task_id,
                started_at=scan.started_at,
                finished_at=scan.finished_at,
                created_at=scan.created_at,
                scenario_name=scenario_name,
                target=target_value,
            )
        )
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _infer_target_type(target: str) -> str:
    """Infer TargetModel.type from the target string."""
    import re

    target = target.strip()

    # CIDR notation
    if re.match(r"^\d{1,3}(\.\d{1,3}){3}/\d+$", target):
        return "cidr"

    # Plain IPv4
    if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", target):
        return "ip"

    # URL
    if target.startswith(("http://", "https://")):
        return "url"

    # Fallback: treat as domain
    return "domain"
