"""Admin endpoints for platform management."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.models import InvestigationModel, ScanResultModel, UserModel
from src.api.v1.auth.dependencies import require_role
from src.core.domain.entities.types import UserRole
from src.core.domain.entities.user import User
from src.dependencies import get_db

router = APIRouter()


class AdminUserResponse(BaseModel):
    id: str
    email: str
    role: str
    subscription_tier: str
    is_active: bool
    is_email_verified: bool
    investigation_count: int = 0
    created_at: str


class PlatformStatsResponse(BaseModel):
    total_users: int
    active_users: int
    total_investigations: int
    total_scans: int
    successful_scans: int
    failed_scans: int


class UpdateUserRoleRequest(BaseModel):
    role: str  # "admin", "analyst", "viewer"


class AuditLogResponse(BaseModel):
    id: str
    user_email: str
    action: str
    resource_type: str
    resource_id: str | None
    details: dict
    ip_address: str | None
    created_at: str


@router.get("/stats", response_model=PlatformStatsResponse)
async def platform_stats(
    current_user: Annotated[User, Depends(require_role(UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PlatformStatsResponse:
    """Return high-level platform statistics."""
    total_users = (await db.execute(select(func.count(UserModel.id)))).scalar() or 0
    active_users = (await db.execute(select(func.count(UserModel.id)).where(UserModel.is_active == True))).scalar() or 0  # noqa: E712
    total_inv = (await db.execute(select(func.count(InvestigationModel.id)))).scalar() or 0
    total_scans = (await db.execute(select(func.count(ScanResultModel.id)))).scalar() or 0
    success_scans = (await db.execute(select(func.count(ScanResultModel.id)).where(ScanResultModel.status == "SUCCESS"))).scalar() or 0
    failed_scans = (await db.execute(select(func.count(ScanResultModel.id)).where(ScanResultModel.status == "FAILED"))).scalar() or 0

    return PlatformStatsResponse(
        total_users=total_users,
        active_users=active_users,
        total_investigations=total_inv,
        total_scans=total_scans,
        successful_scans=success_scans,
        failed_scans=failed_scans,
    )


@router.get("/users", response_model=list[AdminUserResponse])
async def list_users(
    current_user: Annotated[User, Depends(require_role(UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=50, le=200),
) -> list[AdminUserResponse]:
    """List all platform users for admin management."""
    stmt = select(UserModel).order_by(UserModel.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    users = result.scalars().all()
    return [
        AdminUserResponse(
            id=str(u.id),
            email=u.email,
            role=u.role.value if hasattr(u.role, "value") else str(u.role),
            subscription_tier=u.subscription_tier.value if hasattr(u.subscription_tier, "value") else str(u.subscription_tier),
            is_active=u.is_active,
            is_email_verified=u.is_email_verified,
            created_at=u.created_at.isoformat() if u.created_at else "",
        )
        for u in users
    ]


@router.patch("/users/{user_id}/role")
async def update_user_role(
    user_id: UUID,
    body: UpdateUserRoleRequest,
    current_user: Annotated[User, Depends(require_role(UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Change a user's role (admin, analyst, viewer)."""
    user = await db.get(UserModel, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = body.role
    await db.flush()
    return {"status": "updated", "user_id": str(user_id), "new_role": body.role}


@router.patch("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: UUID,
    current_user: Annotated[User, Depends(require_role(UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Toggle a user's active status."""
    user = await db.get(UserModel, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = not user.is_active
    await db.flush()
    return {"status": "toggled", "user_id": str(user_id), "is_active": user.is_active}


@router.get("/audit-log", response_model=list[AuditLogResponse])
async def get_audit_log(
    current_user: Annotated[User, Depends(require_role(UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=100, le=500),
) -> list[AuditLogResponse]:
    """Return the most recent audit log entries."""
    from src.adapters.db.audit_models import AuditLogModel

    stmt = (
        select(AuditLogModel, UserModel.email)
        .join(UserModel, AuditLogModel.user_id == UserModel.id)
        .order_by(AuditLogModel.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [
        AuditLogResponse(
            id=str(row.AuditLogModel.id),
            user_email=row.email,
            action=row.AuditLogModel.action,
            resource_type=row.AuditLogModel.resource_type,
            resource_id=row.AuditLogModel.resource_id,
            details=row.AuditLogModel.details or {},
            ip_address=row.AuditLogModel.ip_address,
            created_at=row.AuditLogModel.created_at.isoformat(),
        )
        for row in result.all()
    ]
