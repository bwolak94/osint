"""FastAPI router — HTTP Fingerprint (tech stack + security headers analysis)."""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.http_fingerprint_models import HttpFingerprintModel
from src.adapters.http_fingerprint.fetcher import fingerprint_url
from src.api.v1.auth.dependencies import get_current_user
from src.api.v1.http_fingerprint.schemas import (
    HttpFingerprintListResponse, HttpFingerprintRequest, HttpFingerprintResponse, SecurityScoreSchema,
)
from src.core.domain.entities.user import User
from src.dependencies import get_db

log = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/", response_model=HttpFingerprintResponse, status_code=status.HTTP_201_CREATED)
async def http_fingerprint(
    body: HttpFingerprintRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HttpFingerprintResponse:
    url = body.url.strip()
    if not url:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="url must not be empty.")

    fp = await fingerprint_url(url)

    result_dict = {
        "url": fp.url,
        "final_url": fp.final_url,
        "status_code": fp.status_code,
        "technologies": fp.technologies,
        "headers": fp.headers,
        "security": {
            "present": fp.security.present,
            "missing": fp.security.missing,
            "score": fp.security.score,
        },
        "cdn": fp.cdn,
        "ip": fp.ip,
        "error": fp.error,
    }

    model = HttpFingerprintModel(
        id=uuid.uuid4(),
        owner_id=current_user.id,
        url=url,
        security_score=fp.security.score,
        result=result_dict,
        created_at=datetime.now(timezone.utc),
    )
    db.add(model)
    await db.flush()

    return HttpFingerprintResponse(
        id=model.id,
        created_at=model.created_at,
        url=fp.url,
        final_url=fp.final_url,
        status_code=fp.status_code,
        technologies=fp.technologies,
        headers=fp.headers,
        security=SecurityScoreSchema(
            present=fp.security.present,
            missing=fp.security.missing,
            score=fp.security.score,
        ),
        cdn=fp.cdn,
        ip=fp.ip,
        error=fp.error,
    )


@router.get("/", response_model=HttpFingerprintListResponse)
async def list_http_fingerprint_scans(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> HttpFingerprintListResponse:
    offset = (page - 1) * page_size
    total = (
        await db.execute(
            select(func.count())
            .select_from(HttpFingerprintModel)
            .where(HttpFingerprintModel.owner_id == current_user.id)
        )
    ).scalar() or 0
    rows = list(
        (
            await db.execute(
                select(HttpFingerprintModel)
                .where(HttpFingerprintModel.owner_id == current_user.id)
                .order_by(HttpFingerprintModel.created_at.desc())
                .limit(page_size)
                .offset(offset)
            )
        ).scalars().all()
    )
    return HttpFingerprintListResponse(
        items=[_to_response(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get("/{scan_id}", response_model=HttpFingerprintResponse)
async def get_http_fingerprint_scan(
    scan_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HttpFingerprintResponse:
    return _to_response(await _get_or_404(db, scan_id, current_user.id))


@router.delete("/{scan_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_http_fingerprint_scan(
    scan_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    model = await _get_or_404(db, scan_id, current_user.id)
    await db.delete(model)
    await db.flush()


async def _get_or_404(db: AsyncSession, scan_id: uuid.UUID, owner_id: uuid.UUID) -> HttpFingerprintModel:
    result = await db.execute(
        select(HttpFingerprintModel).where(
            HttpFingerprintModel.id == scan_id,
            HttpFingerprintModel.owner_id == owner_id,
        )
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found.")
    return model


def _to_response(m: HttpFingerprintModel) -> HttpFingerprintResponse:
    r = m.result or {}
    sec = r.get("security", {})
    return HttpFingerprintResponse(
        id=m.id,
        created_at=m.created_at,
        url=m.url,
        final_url=r.get("final_url"),
        status_code=r.get("status_code"),
        technologies=r.get("technologies", []),
        headers=r.get("headers", {}),
        security=SecurityScoreSchema(
            present=sec.get("present", []),
            missing=sec.get("missing", []),
            score=sec.get("score", 0),
        ),
        cdn=r.get("cdn"),
        ip=r.get("ip"),
        error=r.get("error"),
    )
