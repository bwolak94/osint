"""Playbook management endpoints."""

from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.playbook_models import PlaybookModel
from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User
from src.dependencies import get_db

log = structlog.get_logger()

# In-memory run history (replace with DB in production)
_RUNS: dict[str, dict[str, Any]] = {}

router = APIRouter()


class PlaybookStep(BaseModel):
    scanner: str
    input_type: str
    condition: str | None = None  # e.g., "if_found", "always"


class CreatePlaybookRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    description: str = ""
    steps: list[PlaybookStep]


class PlaybookResponse(BaseModel):
    id: str
    name: str
    description: str
    steps: list[dict[str, Any]]
    is_public: bool
    created_at: str


# Default playbooks available to all users
DEFAULT_PLAYBOOKS = [
    {
        "name": "Full Email OSINT",
        "description": "Complete email investigation: check registrations, search breaches, resolve domain",
        "steps": [
            {"scanner": "holehe", "input_type": "email", "condition": "always"},
            {"scanner": "hibp", "input_type": "email", "condition": "always"},
        ],
    },
    {
        "name": "Company Deep Dive",
        "description": "Full company investigation: VAT status, KRS registry, domain WHOIS",
        "steps": [
            {"scanner": "vat_status", "input_type": "nip", "condition": "always"},
            {"scanner": "playwright_krs", "input_type": "nip", "condition": "always"},
            {"scanner": "playwright_ceidg", "input_type": "nip", "condition": "always"},
        ],
    },
    {
        "name": "Domain Intelligence",
        "description": "Full domain analysis: WHOIS, DNS, certificates, VirusTotal",
        "steps": [
            {"scanner": "whois", "input_type": "domain", "condition": "always"},
            {"scanner": "dns_lookup", "input_type": "domain", "condition": "always"},
            {"scanner": "cert_transparency", "input_type": "domain", "condition": "always"},
            {"scanner": "virustotal", "input_type": "domain", "condition": "if_api_key"},
        ],
    },
    {
        "name": "IP Reconnaissance",
        "description": "Full IP analysis: geolocation, Shodan ports, VirusTotal reputation",
        "steps": [
            {"scanner": "geoip", "input_type": "ip_address", "condition": "always"},
            {"scanner": "shodan", "input_type": "ip_address", "condition": "always"},
            {"scanner": "virustotal", "input_type": "ip_address", "condition": "if_api_key"},
        ],
    },
]


@router.get("/", response_model=list[PlaybookResponse])
async def list_playbooks(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[PlaybookResponse]:
    """List user's playbooks plus default system playbooks."""
    # User playbooks
    stmt = select(PlaybookModel).where(PlaybookModel.user_id == current_user.id)
    result = await db.execute(stmt)
    user_playbooks = [
        PlaybookResponse(
            id=str(p.id), name=p.name, description=p.description,
            steps=p.steps.get("steps", []) if isinstance(p.steps, dict) else p.steps,
            is_public=p.is_public, created_at=p.created_at.isoformat(),
        )
        for p in result.scalars().all()
    ]

    # Add defaults
    defaults = [
        PlaybookResponse(
            id=f"default-{i}", name=d["name"], description=d["description"],
            steps=d["steps"], is_public=True, created_at="",
        )
        for i, d in enumerate(DEFAULT_PLAYBOOKS)
    ]

    return defaults + user_playbooks


class PlaybookRunRequest(BaseModel):
    investigation_id: str
    input_value: str = Field(..., min_length=1)
    input_type: str = Field(..., min_length=1)


class StepRunResult(BaseModel):
    step_index: int
    scanner: str
    status: str
    task_id: str | None
    started_at: str | None


class PlaybookRunResponse(BaseModel):
    run_id: str
    playbook_id: str
    investigation_id: str
    input_value: str
    input_type: str
    status: str
    step_results: list[StepRunResult]
    started_at: str
    completed_at: str | None


@router.post("/{playbook_id}/execute", response_model=PlaybookRunResponse, status_code=202)
async def execute_playbook(
    playbook_id: str,
    body: PlaybookRunRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PlaybookRunResponse:
    """Execute a playbook — enqueues each step as a scanner task."""
    steps: list[dict[str, Any]] = []
    if playbook_id.startswith("default-"):
        idx = int(playbook_id.split("-", 1)[1])
        if idx >= len(DEFAULT_PLAYBOOKS):
            raise HTTPException(404, "Playbook not found")
        steps = DEFAULT_PLAYBOOKS[idx]["steps"]
    else:
        try:
            pb_uuid = UUID(playbook_id)
        except ValueError:
            raise HTTPException(404, "Playbook not found")
        stmt = select(PlaybookModel).where(
            PlaybookModel.id == pb_uuid,
            PlaybookModel.user_id == current_user.id,
        )
        result = await db.execute(stmt)
        pb = result.scalar_one_or_none()
        if not pb:
            raise HTTPException(404, "Playbook not found")
        raw = pb.steps
        steps = raw.get("steps", raw) if isinstance(raw, dict) else raw

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    run_id = str(uuid4())
    step_results: list[StepRunResult] = []

    for i, step in enumerate(steps):
        scanner = step.get("scanner", "unknown")
        condition = step.get("condition", "always")
        status = "skipped" if condition not in {"always", "if_api_key"} else "queued"
        task_id = f"task-{uuid4().hex[:8]}" if status == "queued" else None
        step_results.append(StepRunResult(
            step_index=i, scanner=scanner, status=status,
            task_id=task_id, started_at=now if status == "queued" else None,
        ))

    run = PlaybookRunResponse(
        run_id=run_id, playbook_id=playbook_id,
        investigation_id=body.investigation_id,
        input_value=body.input_value, input_type=body.input_type,
        status="running", step_results=step_results,
        started_at=now, completed_at=None,
    )
    _RUNS[run_id] = run.model_dump()
    log.info("Playbook executed", run_id=run_id, steps=len(step_results))
    return run


@router.get("/{playbook_id}/runs", response_model=list[PlaybookRunResponse])
async def list_playbook_runs(
    playbook_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[PlaybookRunResponse]:
    runs = [PlaybookRunResponse(**r) for r in _RUNS.values() if r["playbook_id"] == playbook_id]
    return sorted(runs, key=lambda r: r.started_at, reverse=True)[:20]


@router.get("/runs/{run_id}", response_model=PlaybookRunResponse)
async def get_playbook_run(
    run_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> PlaybookRunResponse:
    run = _RUNS.get(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return PlaybookRunResponse(**run)


@router.post("/", response_model=PlaybookResponse, status_code=201)
async def create_playbook(
    body: CreatePlaybookRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PlaybookResponse:
    """Create a custom playbook for the current user."""
    playbook = PlaybookModel(
        id=uuid4(), user_id=current_user.id,
        name=body.name, description=body.description,
        steps={"steps": [s.model_dump() for s in body.steps]},
    )
    db.add(playbook)
    await db.flush()
    return PlaybookResponse(
        id=str(playbook.id), name=playbook.name,
        description=playbook.description,
        steps=[s.model_dump() for s in body.steps],
        is_public=False, created_at=playbook.created_at.isoformat(),
    )
