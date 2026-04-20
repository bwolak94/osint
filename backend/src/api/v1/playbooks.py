"""Playbook management endpoints."""

from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.playbook_models import PlaybookModel
from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User
from src.dependencies import get_db

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
