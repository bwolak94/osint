"""FastAPI router for the Facebook Intel module."""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.facebook_intel_models import FacebookIntelModel
from src.api.v1.auth.dependencies import get_current_user
from src.api.v1.facebook_intel.schemas import (
    FacebookIntelListResponse,
    FacebookIntelRequest,
    FacebookIntelResponse,
    FacebookProfileSchema,
)
from src.core.domain.entities.user import User
from src.dependencies import get_db

log = structlog.get_logger(__name__)

router = APIRouter()

# How long (seconds) to wait for the heavy-queue Playwright task before giving up
_CELERY_TIMEOUT = 45


@router.post("/", response_model=FacebookIntelResponse, status_code=status.HTTP_201_CREATED)
async def scan_facebook_intel(
    body: FacebookIntelRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FacebookIntelResponse:
    if not body.query.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="query must not be empty.")

    profiles_json = await _run_scan(body.query.strip(), body.query_type)

    model = FacebookIntelModel(
        id=uuid.uuid4(),
        created_at=datetime.now(timezone.utc),
        owner_id=current_user.id,
        query=body.query.strip(),
        query_type=body.query_type,
        total_results=len(profiles_json),
        results=profiles_json,
    )
    db.add(model)
    await db.flush()

    return _to_response(model)


@router.get("/", response_model=FacebookIntelListResponse)
async def list_facebook_intel_scans(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> FacebookIntelListResponse:
    offset = (page - 1) * page_size
    total = (
        await db.execute(
            select(func.count())
            .select_from(FacebookIntelModel)
            .where(FacebookIntelModel.owner_id == current_user.id)
        )
    ).scalar() or 0
    rows = list(
        (
            await db.execute(
                select(FacebookIntelModel)
                .where(FacebookIntelModel.owner_id == current_user.id)
                .order_by(FacebookIntelModel.created_at.desc())
                .limit(page_size)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return FacebookIntelListResponse(
        items=[_to_response(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get("/{scan_id}", response_model=FacebookIntelResponse)
async def get_facebook_intel_scan(
    scan_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FacebookIntelResponse:
    return _to_response(await _get_or_404(db, scan_id, current_user.id))


@router.delete("/{scan_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_facebook_intel_scan(
    scan_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    model = await _get_or_404(db, scan_id, current_user.id)
    await db.delete(model)
    await db.flush()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _run_scan(query: str, query_type: str) -> list[dict]:
    """Try Celery heavy task first; fall back to httpx-based scanner."""
    # 1. Try dispatching to the heavy (Playwright) worker
    try:
        result = await _dispatch_celery(query, query_type)
        if result is not None:
            return result
    except Exception as exc:
        log.warning("facebook_intel_celery_failed", query=query, error=str(exc))

    # 2. Fall back to the pure-httpx scanner (no Playwright required)
    try:
        from src.adapters.facebook_intel.scanner import FacebookIntelScanner
        scanner = FacebookIntelScanner()
        fb_result = await scanner.scan(query, query_type)  # type: ignore[arg-type]
        return [
            {
                "uid": p.uid,
                "name": p.name,
                "username": p.username,
                "profile_url": p.profile_url,
                "avatar_url": p.avatar_url,
                "cover_url": p.cover_url,
                "bio": p.bio,
                "location": p.location,
                "hometown": p.hometown,
                "work": p.work,
                "education": p.education,
                "followers": p.followers,
                "friends": p.friends,
                "public_posts": p.public_posts,
                "verified": p.verified,
                "category": p.category,
                "source": p.source,
            }
            for p in fb_result.profiles
        ]
    except Exception as exc:
        log.error("facebook_intel_fallback_failed", query=query, error=str(exc))
        return []


async def _dispatch_celery(query: str, query_type: str) -> list[dict] | None:
    """Dispatch to the heavy Celery worker and await result synchronously.

    Returns None if the worker is unavailable or times out.
    """
    import asyncio

    loop = asyncio.get_event_loop()

    def _send_and_get() -> list[dict] | None:
        try:
            from src.workers.tasks.facebook_intel_task import facebook_intel_scrape_task
            task = facebook_intel_scrape_task.apply_async(
                args=[query, query_type],
                queue="heavy",
            )
            raw = task.get(timeout=_CELERY_TIMEOUT, propagate=True)
            return raw.get("profiles", [])
        except Exception:
            return None

    result = await loop.run_in_executor(None, _send_and_get)
    return result


async def _get_or_404(db: AsyncSession, scan_id: uuid.UUID, owner_id: uuid.UUID) -> FacebookIntelModel:
    result = await db.execute(
        select(FacebookIntelModel).where(
            FacebookIntelModel.id == scan_id,
            FacebookIntelModel.owner_id == owner_id,
        )
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found.")
    return model


def _to_response(model: FacebookIntelModel) -> FacebookIntelResponse:
    profiles = [FacebookProfileSchema(**p) for p in (model.results or [])]
    return FacebookIntelResponse(
        id=model.id,
        query=model.query,
        query_type=model.query_type,
        total_results=model.total_results,
        results=profiles,
        created_at=model.created_at,
    )
