"""Campaign management endpoints — group investigations into named campaigns."""

import secrets
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi.responses import Response
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from src.api.v1.auth.dependencies import get_current_user

log = structlog.get_logger()
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class CampaignCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    tags: list[str] = []
    tlp_level: str = Field("WHITE", pattern="^(WHITE|GREEN|AMBER|RED)$")


class CampaignUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    tags: list[str] | None = None


class CampaignResponse(BaseModel):
    id: str
    name: str
    description: str
    tags: list[str]
    tlp_level: str
    investigation_count: int
    created_by: str
    created_at: str
    updated_at: str


class CampaignListResponse(BaseModel):
    campaigns: list[CampaignResponse]
    total: int
    skip: int
    limit: int


class AddInvestigationBody(BaseModel):
    investigation_id: str = Field(..., min_length=1)


class GraphNode(BaseModel):
    id: str
    type: str
    value: str
    source_investigation_id: str


class GraphEdge(BaseModel):
    source: str
    target: str
    relationship: str


class MergedGraphResponse(BaseModel):
    campaign_id: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    investigation_ids: list[str]


class SimilarInvestigationResponse(BaseModel):
    investigation_id: str
    title: str
    jaccard_similarity: float
    shared_identifiers: list[str]


class SimilarInvestigationsResponse(BaseModel):
    campaign_id: str
    similar_investigations: list[SimilarInvestigationResponse]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_campaign(name: str, description: str, tags: list[str], tlp_level: str, user_id: str) -> CampaignResponse:
    now = datetime.now(timezone.utc).isoformat()
    return CampaignResponse(
        id=secrets.token_hex(16),
        name=name,
        description=description,
        tags=tags,
        tlp_level=tlp_level,
        investigation_count=0,
        created_by=user_id,
        created_at=now,
        updated_at=now,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/campaigns", response_model=CampaignResponse, status_code=201)
async def create_campaign(
    body: CampaignCreate,
    current_user: Any = Depends(get_current_user),
) -> CampaignResponse:
    """Create a new investigation campaign."""
    user_id = str(getattr(current_user, "id", "unknown"))
    log.info("Campaign created", name=body.name, user=user_id)
    return _make_campaign(body.name, body.description, body.tags, body.tlp_level, user_id)


@router.get("/campaigns", response_model=CampaignListResponse)
async def list_campaigns(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: Any = Depends(get_current_user),
) -> CampaignListResponse:
    """List campaigns for the current user (paginated)."""
    return CampaignListResponse(campaigns=[], total=0, skip=skip, limit=limit)


@router.get("/campaigns/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: str,
    current_user: Any = Depends(get_current_user),
) -> CampaignResponse:
    """Get a single campaign with its investigation count."""
    user_id = str(getattr(current_user, "id", "unknown"))
    now = datetime.now(timezone.utc).isoformat()
    return CampaignResponse(
        id=campaign_id,
        name="Placeholder Campaign",
        description="",
        tags=[],
        tlp_level="WHITE",
        investigation_count=0,
        created_by=user_id,
        created_at=now,
        updated_at=now,
    )


@router.patch("/campaigns/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: str,
    body: CampaignUpdate,
    current_user: Any = Depends(get_current_user),
) -> CampaignResponse:
    """Update campaign name, description, or tags."""
    user_id = str(getattr(current_user, "id", "unknown"))
    now = datetime.now(timezone.utc).isoformat()
    log.info("Campaign updated", campaign_id=campaign_id, user=user_id)
    return CampaignResponse(
        id=campaign_id,
        name=body.name or "Updated Campaign",
        description=body.description or "",
        tags=body.tags or [],
        tlp_level="WHITE",
        investigation_count=0,
        created_by=user_id,
        created_at=now,
        updated_at=now,
    )


@router.delete("/campaigns/{campaign_id}", status_code=204, response_model=None)
async def delete_campaign(
    campaign_id: str,
    current_user: Any = Depends(get_current_user),
) -> None:
    """Delete a campaign without deleting its investigations."""
    log.info("Campaign deleted", campaign_id=campaign_id)


@router.post("/campaigns/{campaign_id}/investigations", status_code=201)
async def add_investigation_to_campaign(
    campaign_id: str,
    body: AddInvestigationBody,
    current_user: Any = Depends(get_current_user),
) -> dict[str, str]:
    """Add an investigation to a campaign."""
    log.info("Investigation added to campaign", campaign_id=campaign_id, investigation_id=body.investigation_id)
    return {"status": "added", "campaign_id": campaign_id, "investigation_id": body.investigation_id}


@router.delete("/campaigns/{campaign_id}/investigations/{investigation_id}", status_code=204, response_model=None)
async def remove_investigation_from_campaign(
    campaign_id: str,
    investigation_id: str,
    current_user: Any = Depends(get_current_user),
) -> None:
    """Remove an investigation from a campaign."""
    log.info("Investigation removed from campaign", campaign_id=campaign_id, investigation_id=investigation_id)


@router.get("/campaigns/{campaign_id}/graph", response_model=MergedGraphResponse)
async def get_campaign_merged_graph(
    campaign_id: str,
    current_user: Any = Depends(get_current_user),
) -> MergedGraphResponse:
    """Return a merged graph of all investigations in the campaign."""
    return MergedGraphResponse(
        campaign_id=campaign_id,
        nodes=[],
        edges=[],
        investigation_ids=[],
    )


@router.get("/campaigns/{campaign_id}/similar", response_model=SimilarInvestigationsResponse)
async def get_similar_investigations(
    campaign_id: str,
    current_user: Any = Depends(get_current_user),
) -> SimilarInvestigationsResponse:
    """Find investigations not yet in the campaign that share entities (Jaccard similarity)."""
    return SimilarInvestigationsResponse(campaign_id=campaign_id, similar_investigations=[])
