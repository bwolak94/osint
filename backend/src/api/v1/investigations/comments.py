"""Comment endpoints for investigation annotations."""

from typing import Annotated
from uuid import UUID, uuid4

from fastapi.responses import Response
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.comment_models import CommentModel
from src.adapters.db.models import UserModel
from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User
from src.dependencies import get_db

router = APIRouter()


class CreateCommentRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    target_type: str = "investigation"  # "investigation", "node", "edge"
    target_id: str | None = None


class CommentResponse(BaseModel):
    id: str
    user_email: str
    text: str
    target_type: str
    target_id: str | None
    created_at: str


@router.get("/{investigation_id}/comments", response_model=list[CommentResponse])
async def list_comments(
    investigation_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[CommentResponse]:
    stmt = (
        select(CommentModel, UserModel.email)
        .join(UserModel, CommentModel.user_id == UserModel.id)
        .where(CommentModel.investigation_id == investigation_id)
        .order_by(CommentModel.created_at.desc())
    )
    result = await db.execute(stmt)
    return [
        CommentResponse(
            id=str(row.CommentModel.id),
            user_email=row.email,
            text=row.CommentModel.text,
            target_type=row.CommentModel.target_type,
            target_id=row.CommentModel.target_id,
            created_at=row.CommentModel.created_at.isoformat(),
        )
        for row in result.all()
    ]


@router.post("/{investigation_id}/comments", response_model=CommentResponse, status_code=201)
async def create_comment(
    investigation_id: UUID,
    body: CreateCommentRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CommentResponse:
    comment = CommentModel(
        id=uuid4(),
        investigation_id=investigation_id,
        user_id=current_user.id,
        target_type=body.target_type,
        target_id=body.target_id,
        text=body.text,
    )
    db.add(comment)
    await db.flush()
    return CommentResponse(
        id=str(comment.id),
        user_email=str(current_user.email),
        text=comment.text,
        target_type=comment.target_type,
        target_id=comment.target_id,
        created_at=comment.created_at.isoformat(),
    )


@router.delete("/{investigation_id}/comments/{comment_id}", status_code=204, response_model=None)
async def delete_comment(
    investigation_id: UUID,
    comment_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    comment = await db.get(CommentModel, comment_id)
    if not comment or comment.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Comment not found")
    await db.delete(comment)
    await db.flush()
