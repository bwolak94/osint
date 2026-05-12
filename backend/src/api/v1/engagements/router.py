"""Engagement management API — CRUD + target + scope validation."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.pentest_models import PentestAuditLogModel

from src.adapters.audit.pentest_actions import PentestAction
from src.adapters.audit.pentest_audit_service import AuditService
from src.adapters.db.pentest_models import EngagementModel, TargetModel
from src.adapters.security.scope_validator import ScopeRules, ScopeViolation, ScopeValidator
from src.api.v1.auth.dependencies import get_current_user
from src.api.v1.engagements.schemas import (
    AddTargetRequest,
    CreateEngagementRequest,
    EngagementResponse,
    PaginatedEngagementsResponse,
    ScopeRulesSchema,
    ScopeValidateRequest,
    ScopeValidateResponse,
    TargetResponse,
    UpdateEngagementRequest,
)
from src.api.v1.pentesting.dependencies import require_pentester
from src.core.domain.entities.user import User
from src.dependencies import get_db

log = structlog.get_logger(__name__)
router = APIRouter(tags=["engagements"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
UserDep = Annotated[User, Depends(require_pentester)]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _check_and_lock_on_violations(
    db: AsyncSession,
    engagement_id: uuid.UUID,
    user_id: uuid.UUID,
    audit: "AuditService",
) -> None:
    """Lock engagement if ≥3 scope violations occurred in the past hour."""
    one_hour_ago = _utcnow() - timedelta(hours=1)
    count_stmt = (
        select(func.count())
        .select_from(PentestAuditLogModel)
        .where(
            PentestAuditLogModel.entity_id == str(engagement_id),
            PentestAuditLogModel.action == PentestAction.SCOPE_VIOLATION,
            PentestAuditLogModel.ts >= one_hour_ago,
        )
    )
    recent_violations: int = (await db.execute(count_stmt)).scalar_one()

    if recent_violations >= 3:
        eng_stmt = select(EngagementModel).where(EngagementModel.id == engagement_id)
        engagement = (await db.execute(eng_stmt)).scalar_one_or_none()
        if engagement and engagement.status == "active":
            engagement.status = "locked"
            await db.flush()
            await audit.log(
                action=PentestAction.ENGAGEMENT_LOCKED,
                user_id=user_id,
                entity="engagement",
                entity_id=str(engagement_id),
                payload={"reason": "3 scope violations in 1 hour"},
            )
            await log.awarn(
                "engagement_auto_locked",
                engagement_id=str(engagement_id),
                violations=recent_violations,
            )


def _engagement_or_404(engagement: EngagementModel | None) -> EngagementModel:
    if engagement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Engagement not found.")
    return engagement


def _to_engagement_response(m: EngagementModel) -> EngagementResponse:
    return EngagementResponse(
        id=m.id,
        created_by=m.created_by,
        name=m.name,
        client_name=m.client_name,
        roe_hash=m.roe_hash,
        scope_rules=m.scope_rules,
        start_at=m.start_at,
        expires_at=m.expires_at,
        status=m.status,
        created_at=m.created_at,
    )


# ---------------------------------------------------------------------------
# POST /engagements — create with optional RoE file upload
# ---------------------------------------------------------------------------


@router.post("", status_code=status.HTTP_201_CREATED, response_model=EngagementResponse)
async def create_engagement(
    current_user: UserDep,
    db: DbDep,
    body: str = Form(..., description="JSON-encoded CreateEngagementRequest"),
    roe_file: UploadFile | None = File(default=None),
) -> EngagementResponse:
    """Create a new pentest engagement.

    Accepts multipart/form-data: a JSON body field plus an optional PDF RoE file.
    The SHA-256 of the uploaded file is stored as `roe_hash`; actual MinIO upload
    is deferred for the full implementation.
    """
    try:
        request = CreateEngagementRequest.model_validate_json(body)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    roe_hash: str | None = None
    roe_storage_ref: str | None = None
    engagement_id = uuid.uuid4()

    if roe_file is not None:
        content = await roe_file.read()
        roe_hash = hashlib.sha256(content).hexdigest()
        # Upload RoE PDF to MinIO bucket 'engagement-roe'
        try:
            from io import BytesIO
            from src.config import get_settings
            from minio import Minio

            cfg = get_settings()
            minio_client = Minio(
                cfg.minio_endpoint,
                access_key=cfg.minio_access_key,
                secret_key=cfg.minio_secret_key,
                secure=cfg.minio_secure,
            )
            bucket = "engagement-roe"
            if not minio_client.bucket_exists(bucket):
                minio_client.make_bucket(bucket)
            object_key = f"{current_user.id}/{engagement_id}/roe.pdf"
            minio_client.put_object(
                bucket,
                object_key,
                BytesIO(content),
                length=len(content),
                content_type="application/pdf",
            )
            roe_storage_ref = f"{bucket}/{object_key}"
            await log.ainfo(
                "roe_file_uploaded",
                filename=roe_file.filename,
                sha256=roe_hash,
                storage_ref=roe_storage_ref,
            )
        except Exception as exc:
            await log.awarn("roe_upload_failed", error=str(exc))

    engagement = EngagementModel(
        id=engagement_id,
        created_by=current_user.id,
        name=request.name,
        client_name=request.client_name,
        roe_hash=roe_hash,
        roe_storage_ref=roe_storage_ref,
        scope_rules=request.scope_rules.model_dump(),
        start_at=request.start_at,
        expires_at=request.expires_at,
        status="active",
        created_at=_utcnow(),
    )
    db.add(engagement)
    await db.flush()

    audit = AuditService(db)
    await audit.log(
        action=PentestAction.ENGAGEMENT_CREATED,
        user_id=current_user.id,
        entity="engagement",
        entity_id=str(engagement.id),
        payload={"name": request.name, "client_name": request.client_name},
    )

    return _to_engagement_response(engagement)


# ---------------------------------------------------------------------------
# GET /engagements — paginated list
# ---------------------------------------------------------------------------


@router.get("", response_model=PaginatedEngagementsResponse)
async def list_engagements(
    current_user: UserDep,
    db: DbDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> PaginatedEngagementsResponse:
    count_stmt = (
        select(func.count())
        .select_from(EngagementModel)
        .where(EngagementModel.created_by == current_user.id)
    )
    total: int = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(EngagementModel)
        .where(EngagementModel.created_by == current_user.id)
        .order_by(EngagementModel.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return PaginatedEngagementsResponse(
        items=[_to_engagement_response(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# GET /engagements/{id}
# ---------------------------------------------------------------------------


@router.get("/{engagement_id}", response_model=EngagementResponse)
async def get_engagement(
    engagement_id: uuid.UUID,
    current_user: UserDep,
    db: DbDep,
) -> EngagementResponse:
    stmt = select(EngagementModel).where(EngagementModel.id == engagement_id)
    engagement = (await db.execute(stmt)).scalar_one_or_none()
    _engagement_or_404(engagement)
    return _to_engagement_response(engagement)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# PATCH /engagements/{id}
# ---------------------------------------------------------------------------


@router.patch("/{engagement_id}", response_model=EngagementResponse)
async def update_engagement(
    engagement_id: uuid.UUID,
    request: UpdateEngagementRequest,
    current_user: UserDep,
    db: DbDep,
) -> EngagementResponse:
    stmt = select(EngagementModel).where(EngagementModel.id == engagement_id)
    engagement = (await db.execute(stmt)).scalar_one_or_none()
    _engagement_or_404(engagement)
    assert engagement is not None

    if request.name is not None:
        engagement.name = request.name
    if request.client_name is not None:
        engagement.client_name = request.client_name
    if request.scope_rules is not None:
        engagement.scope_rules = request.scope_rules.model_dump()
    if request.start_at is not None:
        engagement.start_at = request.start_at
    if request.expires_at is not None:
        engagement.expires_at = request.expires_at
    if request.status is not None:
        engagement.status = request.status

    await db.flush()

    audit = AuditService(db)
    await audit.log(
        action=PentestAction.ENGAGEMENT_UPDATED,
        user_id=current_user.id,
        entity="engagement",
        entity_id=str(engagement.id),
        payload=request.model_dump(exclude_none=True),
    )
    return _to_engagement_response(engagement)


# ---------------------------------------------------------------------------
# DELETE /engagements/{id} — soft delete
# ---------------------------------------------------------------------------


@router.delete("/{engagement_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def cancel_engagement(
    engagement_id: uuid.UUID,
    current_user: UserDep,
    db: DbDep,
) -> None:
    stmt = select(EngagementModel).where(EngagementModel.id == engagement_id)
    engagement = (await db.execute(stmt)).scalar_one_or_none()
    _engagement_or_404(engagement)
    assert engagement is not None

    engagement.status = "cancelled"
    await db.flush()

    audit = AuditService(db)
    await audit.log(
        action=PentestAction.ENGAGEMENT_CANCELLED,
        user_id=current_user.id,
        entity="engagement",
        entity_id=str(engagement.id),
        payload={},
    )


# ---------------------------------------------------------------------------
# POST /engagements/{id}/targets
# ---------------------------------------------------------------------------


@router.post(
    "/{engagement_id}/targets",
    status_code=status.HTTP_201_CREATED,
    response_model=TargetResponse,
)
async def add_target(
    engagement_id: uuid.UUID,
    request: AddTargetRequest,
    current_user: UserDep,
    db: DbDep,
) -> TargetResponse:
    stmt = select(EngagementModel).where(EngagementModel.id == engagement_id)
    engagement = (await db.execute(stmt)).scalar_one_or_none()
    _engagement_or_404(engagement)
    assert engagement is not None

    if engagement.status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot add targets to a non-active engagement.",
        )

    target = TargetModel(
        id=uuid.uuid4(),
        engagement_id=engagement_id,
        type=request.type,
        value=request.value,
        validated_at=None,
        metadata_={},
    )
    db.add(target)
    await db.flush()

    audit = AuditService(db)
    await audit.log(
        action=PentestAction.TARGET_ADDED,
        user_id=current_user.id,
        entity="target",
        entity_id=str(target.id),
        payload={"type": request.type, "value": request.value},
    )

    return TargetResponse(
        id=target.id,
        engagement_id=target.engagement_id,
        type=target.type,
        value=target.value,
        validated_at=target.validated_at,
        metadata=target.metadata_,
    )


# ---------------------------------------------------------------------------
# GET /engagements/{id}/targets — list targets for an engagement
# ---------------------------------------------------------------------------


@router.get("/{engagement_id}/targets", response_model=list[TargetResponse])
async def list_targets(
    engagement_id: uuid.UUID,
    current_user: UserDep,
    db: DbDep,
) -> list[TargetResponse]:
    stmt = select(EngagementModel).where(EngagementModel.id == engagement_id)
    engagement = (await db.execute(stmt)).scalar_one_or_none()
    _engagement_or_404(engagement)

    tgt_stmt = (
        select(TargetModel)
        .where(TargetModel.engagement_id == engagement_id)
        .order_by(TargetModel.value.asc())
    )
    rows = (await db.execute(tgt_stmt)).scalars().all()
    return [
        TargetResponse(
            id=r.id,
            engagement_id=r.engagement_id,
            type=r.type,
            value=r.value,
            validated_at=r.validated_at,
            metadata=r.metadata_,
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# POST /engagements/{id}/scope/validate
# ---------------------------------------------------------------------------


@router.post("/{engagement_id}/scope/validate", response_model=ScopeValidateResponse)
async def validate_scope(
    engagement_id: uuid.UUID,
    request: ScopeValidateRequest,
    current_user: UserDep,
    db: DbDep,
) -> ScopeValidateResponse:
    stmt = select(EngagementModel).where(EngagementModel.id == engagement_id)
    engagement = (await db.execute(stmt)).scalar_one_or_none()
    _engagement_or_404(engagement)
    assert engagement is not None

    raw = engagement.scope_rules or {}
    rules = ScopeRules(
        allowed_cidrs=raw.get("allowed_cidrs", []),
        allowed_domains=raw.get("allowed_domains", []),
        excluded=raw.get("excluded", []),
    )
    validator = ScopeValidator(rules)

    try:
        match request.type:
            case "ip":
                validator.validate_ip(request.value)
            case "cidr":
                validator.validate_cidr(request.value)
            case "domain":
                validator.validate_domain(request.value)
            case "url":
                validator.validate_url(request.value)
        return ScopeValidateResponse(valid=True)
    except ScopeViolation as exc:
        audit = AuditService(db)
        await audit.log(
            action=PentestAction.SCOPE_VIOLATION,
            user_id=current_user.id,
            entity="engagement",
            entity_id=str(engagement_id),
            payload={"target": request.value, "reason": str(exc)},
        )
        # Auto-lock after 3 violations in 1 hour
        await _check_and_lock_on_violations(db, engagement_id, current_user.id, audit)
        return ScopeValidateResponse(valid=False, reason=str(exc))
