"""Asset tagging endpoints — tags stored in TargetModel.metadata_ JSONB."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.pentest_models import EngagementModel, TargetModel
from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User
from src.dependencies import get_db

log = structlog.get_logger(__name__)
router = APIRouter(tags=["assets"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
UserDep = Annotated[User, Depends(get_current_user)]


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class AssetResponse(BaseModel):
    id: uuid.UUID
    engagement_id: uuid.UUID
    type: str
    value: str
    tags: list[str]
    owner: str | None
    classification: str | None
    asset_value: str | None
    metadata: dict[str, Any]

    model_config = {"from_attributes": True}


class UpdateTagsRequest(BaseModel):
    tags: list[str] | None = None
    owner: str | None = None
    classification: str | None = None
    asset_value: str | None = None


class AssetsListResponse(BaseModel):
    engagement_id: uuid.UUID
    assets: list[AssetResponse]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _target_to_asset(target: TargetModel) -> AssetResponse:
    meta = dict(target.metadata_ or {})
    return AssetResponse(
        id=target.id,
        engagement_id=target.engagement_id,
        type=target.type,
        value=target.value,
        tags=meta.get("tags", []),
        owner=meta.get("owner"),
        classification=meta.get("classification"),
        asset_value=meta.get("asset_value"),
        metadata=meta,
    )


async def _get_engagement_or_404(engagement_id: uuid.UUID, db: AsyncSession) -> EngagementModel:
    stmt = select(EngagementModel).where(EngagementModel.id == engagement_id)
    engagement = (await db.execute(stmt)).scalar_one_or_none()
    if engagement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Engagement not found.")
    return engagement


# ---------------------------------------------------------------------------
# GET /engagements/{id}/assets
# ---------------------------------------------------------------------------


@router.get("/engagements/{engagement_id}/assets", response_model=AssetsListResponse)
async def list_assets(
    engagement_id: uuid.UUID,
    current_user: UserDep,
    db: DbDep,
) -> AssetsListResponse:
    """List all targets (assets) for an engagement with their tags and metadata."""
    await _get_engagement_or_404(engagement_id, db)

    stmt = select(TargetModel).where(TargetModel.engagement_id == engagement_id)
    targets = (await db.execute(stmt)).scalars().all()

    return AssetsListResponse(
        engagement_id=engagement_id,
        assets=[_target_to_asset(t) for t in targets],
    )


# ---------------------------------------------------------------------------
# PATCH /targets/{id}/tags
# ---------------------------------------------------------------------------


@router.patch("/targets/{target_id}/tags", response_model=AssetResponse)
async def update_target_tags(
    target_id: uuid.UUID,
    request: UpdateTagsRequest,
    current_user: UserDep,
    db: DbDep,
) -> AssetResponse:
    """Update tags and asset metadata on a target."""
    stmt = select(TargetModel).where(TargetModel.id == target_id)
    target = (await db.execute(stmt)).scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found.")

    meta = dict(target.metadata_ or {})

    if request.tags is not None:
        meta["tags"] = request.tags
    if request.owner is not None:
        meta["owner"] = request.owner
    if request.classification is not None:
        meta["classification"] = request.classification
    if request.asset_value is not None:
        meta["asset_value"] = request.asset_value

    target.metadata_ = meta
    await db.flush()

    log.info("asset_tags_updated", target_id=str(target_id))
    return _target_to_asset(target)


# ---------------------------------------------------------------------------
# GET /engagements/{id}/assets/by-tag/{tag}
# ---------------------------------------------------------------------------


@router.get(
    "/engagements/{engagement_id}/assets/by-tag/{tag}",
    response_model=AssetsListResponse,
)
async def list_assets_by_tag(
    engagement_id: uuid.UUID,
    tag: str,
    current_user: UserDep,
    db: DbDep,
) -> AssetsListResponse:
    """Filter assets (targets) in an engagement by a specific tag."""
    await _get_engagement_or_404(engagement_id, db)

    stmt = select(TargetModel).where(TargetModel.engagement_id == engagement_id)
    all_targets = (await db.execute(stmt)).scalars().all()

    matched = [
        t for t in all_targets
        if tag in (t.metadata_ or {}).get("tags", [])
    ]

    return AssetsListResponse(
        engagement_id=engagement_id,
        assets=[_target_to_asset(t) for t in matched],
    )
