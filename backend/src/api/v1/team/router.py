"""Team RBAC management for engagements — stored in engagement.scope_rules JSONB."""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.pentest_models import EngagementModel
from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User
from src.dependencies import get_db

log = structlog.get_logger(__name__)
router = APIRouter(tags=["team"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
UserDep = Annotated[User, Depends(get_current_user)]

TeamRole = Literal["lead", "tester", "reviewer", "readonly"]

_TEAM_KEY = "team"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_engagement_or_404(engagement_id: uuid.UUID, db: AsyncSession) -> EngagementModel:
    stmt = select(EngagementModel).where(EngagementModel.id == engagement_id)
    engagement = (await db.execute(stmt)).scalar_one_or_none()
    if engagement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Engagement not found.")
    return engagement


def _get_team(engagement: EngagementModel) -> list[dict]:
    return list((engagement.scope_rules or {}).get(_TEAM_KEY, []))


def _set_team(engagement: EngagementModel, team: list[dict]) -> None:
    scope_rules = dict(engagement.scope_rules or {})
    scope_rules[_TEAM_KEY] = team
    engagement.scope_rules = scope_rules


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TeamMember(BaseModel):
    user_id: str
    role: TeamRole


class AddTeamMemberRequest(BaseModel):
    user_id: str
    role: TeamRole


class TeamListResponse(BaseModel):
    engagement_id: uuid.UUID
    members: list[TeamMember]


class TeamMemberRoleResponse(BaseModel):
    user_id: str
    role: TeamRole


# ---------------------------------------------------------------------------
# GET /engagements/{id}/team
# ---------------------------------------------------------------------------


@router.get("/engagements/{engagement_id}/team", response_model=TeamListResponse)
async def list_team_members(
    engagement_id: uuid.UUID,
    current_user: UserDep,
    db: DbDep,
) -> TeamListResponse:
    """List all team members assigned to an engagement."""
    engagement = await _get_engagement_or_404(engagement_id, db)
    team = _get_team(engagement)
    return TeamListResponse(
        engagement_id=engagement_id,
        members=[TeamMember(user_id=m["user_id"], role=m["role"]) for m in team],
    )


# ---------------------------------------------------------------------------
# POST /engagements/{id}/team
# ---------------------------------------------------------------------------


@router.post(
    "/engagements/{engagement_id}/team",
    response_model=TeamListResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_team_member(
    engagement_id: uuid.UUID,
    request: AddTeamMemberRequest,
    current_user: UserDep,
    db: DbDep,
) -> TeamListResponse:
    """Add a team member to an engagement (or update their role if already present)."""
    engagement = await _get_engagement_or_404(engagement_id, db)
    team = _get_team(engagement)

    # Update existing entry or append
    for member in team:
        if member["user_id"] == request.user_id:
            member["role"] = request.role
            break
    else:
        team.append({"user_id": request.user_id, "role": request.role})

    _set_team(engagement, team)
    await db.flush()

    log.info(
        "team_member_added",
        engagement_id=str(engagement_id),
        user_id=request.user_id,
        role=request.role,
    )
    return TeamListResponse(
        engagement_id=engagement_id,
        members=[TeamMember(user_id=m["user_id"], role=m["role"]) for m in team],
    )


# ---------------------------------------------------------------------------
# DELETE /engagements/{id}/team/{user_id}
# ---------------------------------------------------------------------------


@router.delete(
    "/engagements/{engagement_id}/team/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT, response_model=None,
    
)
async def remove_team_member(
    engagement_id: uuid.UUID,
    user_id: str,
    current_user: UserDep,
    db: DbDep,
) -> None:
    """Remove a team member from an engagement."""
    engagement = await _get_engagement_or_404(engagement_id, db)
    team = _get_team(engagement)

    filtered = [m for m in team if m["user_id"] != user_id]
    if len(filtered) == len(team):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id!r} is not a member of this engagement.",
        )

    _set_team(engagement, filtered)
    await db.flush()

    log.info("team_member_removed", engagement_id=str(engagement_id), user_id=user_id)


# ---------------------------------------------------------------------------
# GET /engagements/{id}/team/{user_id}/role
# ---------------------------------------------------------------------------


@router.get(
    "/engagements/{engagement_id}/team/{user_id}/role",
    response_model=TeamMemberRoleResponse,
)
async def get_team_member_role(
    engagement_id: uuid.UUID,
    user_id: str,
    current_user: UserDep,
    db: DbDep,
) -> TeamMemberRoleResponse:
    """Get the role of a specific team member within an engagement."""
    engagement = await _get_engagement_or_404(engagement_id, db)
    team = _get_team(engagement)

    for member in team:
        if member["user_id"] == user_id:
            return TeamMemberRoleResponse(user_id=user_id, role=member["role"])

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"User {user_id!r} is not a member of this engagement.",
    )
