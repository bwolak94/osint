"""API key management endpoints — create, list, revoke programmatic access keys."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.pentest_extras_models import ApiKeyModel
from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User
from src.dependencies import get_db

log = structlog.get_logger(__name__)
router = APIRouter(tags=["api-keys"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
UserDep = Annotated[User, Depends(get_current_user)]


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ApiKeyResponse(BaseModel):
    """Safe API key representation — never exposes the full key."""

    id: uuid.UUID
    name: str
    key_prefix: str
    scopes: list[str] | None
    last_used_at: datetime | None
    expires_at: datetime | None
    created_at: datetime
    revoked: bool

    model_config = {"from_attributes": True}


class CreateApiKeyRequest(BaseModel):
    name: str
    scopes: list[str] = []
    expires_at: datetime | None = None


class CreateApiKeyResponse(BaseModel):
    """One-time response that includes the full key — never retrievable again."""

    id: uuid.UUID
    name: str
    key: str  # full key — shown once only
    key_prefix: str
    scopes: list[str] | None
    expires_at: datetime | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key.

    Returns:
        (full_key, key_hash, key_prefix)
    """
    raw = "ptk_" + secrets.token_hex(28)
    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    key_prefix = raw[:8]
    return raw, key_hash, key_prefix


def _to_response(m: ApiKeyModel) -> ApiKeyResponse:
    return ApiKeyResponse(
        id=m.id,
        name=m.name,
        key_prefix=m.key_prefix,
        scopes=m.scopes,
        last_used_at=m.last_used_at,
        expires_at=m.expires_at,
        created_at=m.created_at,
        revoked=m.revoked,
    )


# ---------------------------------------------------------------------------
# GET /api-keys
# ---------------------------------------------------------------------------


@router.get("", response_model=list[ApiKeyResponse])
async def list_api_keys(
    current_user: UserDep,
    db: DbDep,
) -> list[ApiKeyResponse]:
    """List all API keys for the current user — full key is never returned."""
    stmt = (
        select(ApiKeyModel)
        .where(ApiKeyModel.user_id == current_user.id)
        .order_by(ApiKeyModel.created_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_response(r) for r in rows]


# ---------------------------------------------------------------------------
# POST /api-keys
# ---------------------------------------------------------------------------


@router.post("", response_model=CreateApiKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    request: CreateApiKeyRequest,
    current_user: UserDep,
    db: DbDep,
) -> CreateApiKeyResponse:
    """Create a new API key. The full key is returned ONCE and cannot be retrieved again."""
    raw_key, key_hash, key_prefix = _generate_api_key()

    api_key = ApiKeyModel(
        id=uuid.uuid4(),
        user_id=current_user.id,
        name=request.name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        scopes=request.scopes if request.scopes else None,
        expires_at=request.expires_at,
        revoked=False,
    )
    db.add(api_key)
    await db.flush()
    await db.refresh(api_key)

    log.info(
        "api_key_created",
        api_key_id=str(api_key.id),
        user_id=str(current_user.id),
        name=request.name,
        scopes=request.scopes,
    )

    return CreateApiKeyResponse(
        id=api_key.id,
        name=api_key.name,
        key=raw_key,
        key_prefix=key_prefix,
        scopes=api_key.scopes,
        expires_at=api_key.expires_at,
        created_at=api_key.created_at,
    )


# ---------------------------------------------------------------------------
# DELETE /api-keys/{id}
# ---------------------------------------------------------------------------


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def revoke_api_key(
    key_id: uuid.UUID,
    current_user: UserDep,
    db: DbDep,
) -> None:
    """Revoke an API key — sets revoked=True, key can no longer be used for authentication."""
    stmt = select(ApiKeyModel).where(
        ApiKeyModel.id == key_id,
        ApiKeyModel.user_id == current_user.id,
    )
    api_key = (await db.execute(stmt)).scalar_one_or_none()
    if api_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found.")
    if api_key.revoked:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="API key is already revoked."
        )

    api_key.revoked = True
    await db.flush()
    log.info("api_key_revoked", api_key_id=str(key_id), user_id=str(current_user.id))
