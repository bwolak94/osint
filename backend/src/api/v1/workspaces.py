"""Workspace management endpoints."""

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.workspace_models import WorkspaceModel
from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User
from src.dependencies import get_db

router = APIRouter()


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    owner_id: str
    member_count: int
    created_at: str


@router.get("/", response_model=list[WorkspaceResponse])
async def list_workspaces(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[WorkspaceResponse]:
    stmt = select(WorkspaceModel).where(
        (WorkspaceModel.owner_id == current_user.id) |
        (WorkspaceModel.member_ids.any(str(current_user.id)))
    )
    result = await db.execute(stmt)
    return [
        WorkspaceResponse(
            id=str(w.id), name=w.name, owner_id=str(w.owner_id),
            member_count=len(w.member_ids) + 1,
            created_at=w.created_at.isoformat(),
        )
        for w in result.scalars().all()
    ]


@router.post("/", response_model=WorkspaceResponse, status_code=201)
async def create_workspace(
    body: CreateWorkspaceRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WorkspaceResponse:
    workspace = WorkspaceModel(
        id=uuid4(), name=body.name, owner_id=current_user.id, member_ids=[],
    )
    db.add(workspace)
    await db.flush()
    return WorkspaceResponse(
        id=str(workspace.id), name=workspace.name,
        owner_id=str(workspace.owner_id), member_count=1,
        created_at=workspace.created_at.isoformat(),
    )


@router.post("/{workspace_id}/members")
async def add_member(
    workspace_id: UUID,
    body: dict,  # {"user_id": "..."}
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    ws = await db.get(WorkspaceModel, workspace_id)
    if not ws or ws.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Workspace not found")
    user_id = body.get("user_id", "")
    if user_id not in ws.member_ids:
        ws.member_ids = [*ws.member_ids, user_id]
        await db.flush()
    return {"status": "added", "member_count": len(ws.member_ids) + 1}
