"""Role-Based Access Control (RBAC) — 4 roles.

Roles:
  admin    — full access including user/role management
  operator — create/run scans, manage findings
  auditor  — read-only + export
  viewer   — read-only, no exports

Endpoints:
  GET    /api/v1/rbac/roles            — list roles and permissions matrix
  GET    /api/v1/rbac/users            — list users with roles (#35 paginated)
  PUT    /api/v1/rbac/users/{id}/role  — assign role to user
  GET    /api/v1/rbac/audit-log        — RBAC change history (#22)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.auth.dependencies import get_current_user
from src.adapters.db.models import UserModel
from src.core.domain.entities.user import User
from src.dependencies import get_db

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/rbac", tags=["rbac"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
UserDep = Annotated[User, Depends(get_current_user)]

# ---------------------------------------------------------------------------
# Role definitions
# ---------------------------------------------------------------------------

ROLE_PERMISSIONS: dict[str, dict[str, list[str]]] = {
    "admin": {
        "users": ["read", "write", "delete"],
        "investigations": ["read", "write", "delete"],
        "scans": ["read", "write", "delete", "execute"],
        "findings": ["read", "write", "delete"],
        "reports": ["read", "write", "export"],
        "settings": ["read", "write"],
        "rbac": ["read", "write"],
        "audit_log": ["read"],
    },
    "operator": {
        "investigations": ["read", "write"],
        "scans": ["read", "write", "execute"],
        "findings": ["read", "write"],
        "reports": ["read", "write", "export"],
        "settings": ["read"],
        "audit_log": ["read"],
    },
    "auditor": {
        "investigations": ["read"],
        "scans": ["read"],
        "findings": ["read"],
        "reports": ["read", "export"],
        "audit_log": ["read"],
    },
    "viewer": {
        "investigations": ["read"],
        "scans": ["read"],
        "findings": ["read"],
        "reports": ["read"],
    },
}

VALID_ROLES = set(ROLE_PERMISSIONS.keys())

# ---------------------------------------------------------------------------
# In-memory audit trail (#22)  — production: write to audit_log DB table
# ---------------------------------------------------------------------------

_rbac_audit_log: list[dict[str, Any]] = []  # newest last


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class RoleInfo(BaseModel):
    role: str
    permissions: dict[str, list[str]]
    description: str


class UserRoleResponse(BaseModel):
    id: str
    email: str
    role: str
    subscription_tier: str


class AssignRoleRequest(BaseModel):
    role: str


class RbacAuditEntry(BaseModel):
    timestamp: str
    action: str
    target_user_id: str
    target_email: str
    old_role: str
    new_role: str
    by_user_id: str
    by_email: str


# ---------------------------------------------------------------------------
# Permission check helper
# ---------------------------------------------------------------------------


def require_role(*roles: str):
    """FastAPI dependency: raise 403 if current user doesn't have one of the roles."""
    async def check(current_user: Annotated[User, Depends(get_current_user)]):  # type: ignore[misc]
        user_role = getattr(current_user, "role", "viewer")
        if user_role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user_role}' insufficient. Required: {list(roles)}",
            )
        return current_user
    return check


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/roles", response_model=list[RoleInfo])
async def list_roles(current_user: UserDep) -> list[RoleInfo]:  # noqa: ARG001
    descriptions = {
        "admin": "Full platform access including user management and settings",
        "operator": "Create and execute scans, manage findings and reports",
        "auditor": "Read-only access with export capability for compliance",
        "viewer": "Read-only access to investigations, scans, and findings",
    }
    return [
        RoleInfo(role=role, permissions=perms, description=descriptions.get(role, ""))
        for role, perms in ROLE_PERMISSIONS.items()
    ]


@router.get("/users", response_model=list[UserRoleResponse])
async def list_users_with_roles(
    current_user: UserDep,
    db: DbDep,
    limit: int = 50,   # (#35) pagination
    offset: int = 0,
) -> list[UserRoleResponse]:
    """List users with their roles — paginated. (#35)"""
    user_role = getattr(current_user, "role", "viewer")
    if user_role not in ("admin", "auditor"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins and auditors only.")

    stmt = select(UserModel).order_by(UserModel.created_at).offset(offset).limit(min(limit, 200))
    rows = (await db.execute(stmt)).scalars().all()
    return [
        UserRoleResponse(
            id=str(r.id),
            email=r.email,
            role=getattr(r, "role", "viewer"),
            subscription_tier=r.subscription_tier,
        )
        for r in rows
    ]


@router.get("/audit-log", response_model=list[RbacAuditEntry])
async def get_rbac_audit_log(
    current_user: UserDep,
    limit: int = 100,
) -> list[RbacAuditEntry]:
    """Return recent RBAC role-change audit events. (#22)"""
    if getattr(current_user, "role", "viewer") not in ("admin", "auditor"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins and auditors only.")
    return [RbacAuditEntry(**e) for e in _rbac_audit_log[-limit:]]


@router.put("/users/{user_id}/role", response_model=UserRoleResponse)
async def assign_role(
    user_id: UUID,
    body: AssignRoleRequest,
    current_user: UserDep,
    db: DbDep,
) -> UserRoleResponse:
    if getattr(current_user, "role", "viewer") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins only.")

    if body.role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid role. Valid roles: {sorted(VALID_ROLES)}",
        )

    stmt = select(UserModel).where(UserModel.id == user_id)
    target = (await db.execute(stmt)).scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    old_role = getattr(target, "role", "viewer")

    await db.execute(update(UserModel).where(UserModel.id == user_id).values(role=body.role))
    await db.commit()

    # Append to audit trail (#22)
    _rbac_audit_log.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": "role_changed",
        "target_user_id": str(user_id),
        "target_email": target.email,
        "old_role": old_role,
        "new_role": body.role,
        "by_user_id": str(current_user.id),
        "by_email": getattr(current_user, "email", ""),
    })

    await log.ainfo("role_assigned", target=str(user_id), old=old_role, new=body.role, by=str(current_user.id))
    return UserRoleResponse(id=str(target.id), email=target.email, role=body.role, subscription_tier=target.subscription_tier)
