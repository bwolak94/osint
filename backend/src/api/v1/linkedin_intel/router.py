"""FastAPI router for the LinkedIn Intel module."""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.linkedin_intel_models import LinkedInIntelModel
from src.api.v1.auth.dependencies import get_current_user
from src.api.v1.linkedin_intel.schemas import (
    LinkedInIntelListResponse,
    LinkedInIntelRequest,
    LinkedInIntelResponse,
    LinkedInProfileSchema,
)
from src.core.domain.entities.user import User
from src.dependencies import get_db

log = structlog.get_logger(__name__)

router = APIRouter()

_CELERY_TIMEOUT = 90  # LinkedIn scrape via Yahoo dork


@router.post("/", response_model=LinkedInIntelResponse, status_code=status.HTTP_201_CREATED)
async def scan_linkedin_intel(
    body: LinkedInIntelRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LinkedInIntelResponse:
    if not body.query.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="query must not be empty.")

    profiles_json = await _run_scan(body.query.strip(), body.query_type)

    model = LinkedInIntelModel(
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


@router.get("/", response_model=LinkedInIntelListResponse)
async def list_linkedin_intel_scans(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> LinkedInIntelListResponse:
    offset = (page - 1) * page_size
    total = (
        await db.execute(
            select(func.count())
            .select_from(LinkedInIntelModel)
            .where(LinkedInIntelModel.owner_id == current_user.id)
        )
    ).scalar() or 0
    rows = list(
        (
            await db.execute(
                select(LinkedInIntelModel)
                .where(LinkedInIntelModel.owner_id == current_user.id)
                .order_by(LinkedInIntelModel.created_at.desc())
                .limit(page_size)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return LinkedInIntelListResponse(
        items=[_to_response(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get("/{scan_id}", response_model=LinkedInIntelResponse)
async def get_linkedin_intel_scan(
    scan_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LinkedInIntelResponse:
    return _to_response(await _get_or_404(db, scan_id, current_user.id))


@router.delete("/{scan_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_linkedin_intel_scan(
    scan_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    model = await _get_or_404(db, scan_id, current_user.id)
    await db.delete(model)
    await db.flush()


async def _run_scan(query: str, query_type: str) -> list[dict]:
    try:
        result = await _dispatch_celery(query, query_type)
        if result is not None:
            return result
    except Exception as exc:
        log.warning("linkedin_intel_celery_failed", query=query, error=str(exc))
    return []


async def _dispatch_celery(query: str, query_type: str) -> list[dict] | None:
    import asyncio

    loop = asyncio.get_event_loop()

    def _send_and_get() -> list[dict] | None:
        try:
            from src.workers.tasks.linkedin_intel_task import linkedin_intel_scrape_task
            task = linkedin_intel_scrape_task.apply_async(
                args=[query, query_type],
                queue="heavy",
            )
            raw = task.get(timeout=_CELERY_TIMEOUT, propagate=True)
            return raw.get("profiles", [])
        except Exception:
            return None

    return await loop.run_in_executor(None, _send_and_get)


async def _get_or_404(db: AsyncSession, scan_id: uuid.UUID, owner_id: uuid.UUID) -> LinkedInIntelModel:
    result = await db.execute(
        select(LinkedInIntelModel).where(
            LinkedInIntelModel.id == scan_id,
            LinkedInIntelModel.owner_id == owner_id,
        )
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found.")
    return model


def _to_response(model: LinkedInIntelModel) -> LinkedInIntelResponse:
    profiles = [LinkedInProfileSchema(**p) for p in (model.results or [])]
    return LinkedInIntelResponse(
        id=model.id,
        query=model.query,
        query_type=model.query_type,
        total_results=model.total_results,
        results=profiles,
        created_at=model.created_at,
    )
