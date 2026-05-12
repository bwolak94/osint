"""Investigation ACL — fine-grained per-user access control (view / edit / admin)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.database import async_session_factory
from src.adapters.db.models import InvestigationACLModel, InvestigationModel
from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User
from src.utils.time import utcnow

router = APIRouter()

_VALID_PERMISSIONS = {"view", "edit", "admin"}


class ACLEntry(BaseModel):
    model_config = {"json_schema_extra": {"example": {
        "user_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
        "permission": "edit",
    }}}

    user_id: str
    permission: str  # "view" | "edit" | "admin"


class ACLResponse(BaseModel):
    model_config = {"json_schema_extra": {"example": {
        "investigation_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "user_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
        "permission": "edit",
        "granted_by": "1a2b3c4d-5e6f-7890-abcd-ef1234567890",
        "granted_at": "2026-04-25T12:00:00.000000",
    }}}

    investigation_id: str
    user_id: str
    permission: str
    granted_by: str | None
    granted_at: str


async def _assert_admin(inv_id: uuid.UUID, current_user: User, db: AsyncSession) -> None:
    """Raise 403 unless the current user is owner or admin of the investigation."""
    inv = (
        await db.execute(select(InvestigationModel).where(InvestigationModel.id == inv_id))
    ).scalar_one_or_none()
    if inv is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    if str(inv.owner_id) == str(current_user.id):
        return
    acl = (
        await db.execute(
            select(InvestigationACLModel).where(
                InvestigationACLModel.investigation_id == inv_id,
                InvestigationACLModel.user_id == current_user.id,
                InvestigationACLModel.permission == "admin",
            )
        )
    ).scalar_one_or_none()
    if acl is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin permission required")


@router.get(
    "/investigations/{investigation_id}/acl",
    response_model=list[ACLResponse],
    tags=["investigation-acl"],
)
async def list_acl(
    investigation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(lambda: async_session_factory()),
) -> list[ACLResponse]:
    inv_id = uuid.UUID(investigation_id)
    await _assert_admin(inv_id, current_user, db)

    rows = (
        await db.execute(
            select(InvestigationACLModel).where(
                InvestigationACLModel.investigation_id == inv_id
            )
        )
    ).scalars().all()

    return [
        ACLResponse(
            investigation_id=investigation_id,
            user_id=str(row.user_id),
            permission=row.permission,
            granted_by=str(row.granted_by) if row.granted_by else None,
            granted_at=row.granted_at.isoformat(),
        )
        for row in rows
    ]


@router.post(
    "/investigations/{investigation_id}/acl",
    response_model=ACLResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["investigation-acl"],
)
async def grant_access(
    investigation_id: str,
    body: ACLEntry,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(lambda: async_session_factory()),
) -> ACLResponse:
    if body.permission not in _VALID_PERMISSIONS:
        raise HTTPException(status_code=400, detail=f"permission must be one of {_VALID_PERMISSIONS}")

    inv_id = uuid.UUID(investigation_id)
    await _assert_admin(inv_id, current_user, db)

    from sqlalchemy.dialects.postgresql import insert as pg_insert

    target_user_id = uuid.UUID(body.user_id)
    now = utcnow()

    async with db.begin():
        stmt = (
            pg_insert(InvestigationACLModel)
            .values(
                id=uuid.uuid4(),
                investigation_id=inv_id,
                user_id=target_user_id,
                permission=body.permission,
                granted_by=current_user.id,
                granted_at=now,
            )
            .on_conflict_do_update(
                index_elements=["investigation_id", "user_id"],
                set_={"permission": body.permission, "granted_by": current_user.id, "granted_at": now},
            )
        )
        await db.execute(stmt)

    return ACLResponse(
        investigation_id=investigation_id,
        user_id=body.user_id,
        permission=body.permission,
        granted_by=str(current_user.id),
        granted_at=now.isoformat(),
    )


@router.delete(
    "/investigations/{investigation_id}/acl/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT, response_model=None,
    tags=["investigation-acl"],
)
async def revoke_access(
    investigation_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(lambda: async_session_factory()),
) -> None:
    inv_id = uuid.UUID(investigation_id)
    await _assert_admin(inv_id, current_user, db)

    await db.execute(
        delete(InvestigationACLModel).where(
            InvestigationACLModel.investigation_id == inv_id,
            InvestigationACLModel.user_id == uuid.UUID(user_id),
        )
    )
    await db.commit()


# ── Bulk ACL update ───────────────────────────────────────────────────────────


class BulkACLEntry(BaseModel):
    user_id: str
    permission: str  # "view" | "edit" | "admin" | "revoke"


class BulkACLRequest(BaseModel):
    model_config = {"json_schema_extra": {"example": {
        "entries": [
            {"user_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7", "permission": "edit"},
            {"user_id": "1a2b3c4d-5e6f-7890-abcd-ef1234567890", "permission": "revoke"},
        ]
    }}}

    entries: list[BulkACLEntry]


class BulkACLResponse(BaseModel):
    granted: int
    revoked: int
    skipped: int


@router.patch(
    "/investigations/{investigation_id}/acl/bulk",
    response_model=BulkACLResponse,
    tags=["investigation-acl"],
)
async def bulk_update_acl(
    investigation_id: str,
    body: BulkACLRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(lambda: async_session_factory()),
) -> BulkACLResponse:
    """Grant or revoke access for multiple users in a single request.

    Set permission to "revoke" to remove a user's access.
    Invalid UUIDs or unknown permissions are skipped (counted in `skipped`).
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    inv_id = uuid.UUID(investigation_id)
    await _assert_admin(inv_id, current_user, db)

    granted = 0
    revoked = 0
    skipped = 0
    now = utcnow()

    for entry in body.entries:
        if entry.permission not in (_VALID_PERMISSIONS | {"revoke"}):
            skipped += 1
            continue
        try:
            target_user_id = uuid.UUID(entry.user_id)
        except ValueError:
            skipped += 1
            continue

        if entry.permission == "revoke":
            result = await db.execute(
                delete(InvestigationACLModel).where(
                    InvestigationACLModel.investigation_id == inv_id,
                    InvestigationACLModel.user_id == target_user_id,
                )
            )
            if result.rowcount > 0:
                revoked += 1
        else:
            stmt = (
                pg_insert(InvestigationACLModel)
                .values(
                    id=uuid.uuid4(),
                    investigation_id=inv_id,
                    user_id=target_user_id,
                    permission=entry.permission,
                    granted_by=current_user.id,
                    granted_at=now,
                )
                .on_conflict_do_update(
                    index_elements=["investigation_id", "user_id"],
                    set_={"permission": entry.permission, "granted_by": current_user.id, "granted_at": now},
                )
            )
            await db.execute(stmt)
            granted += 1

    await db.commit()
    return BulkACLResponse(granted=granted, revoked=revoked, skipped=skipped)
