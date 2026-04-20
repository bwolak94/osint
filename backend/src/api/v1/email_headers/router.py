"""FastAPI router for Email Header Analyzer module.

Endpoints:
  POST   /api/v1/email-headers/      — Submit raw headers for analysis
  GET    /api/v1/email-headers/      — Paginated history
  GET    /api/v1/email-headers/{id}  — Single record
  DELETE /api/v1/email-headers/{id}  — Delete record (204)
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.email_header_models import EmailHeaderModel
from src.adapters.email_header.parser import EmailHeaderParser
from src.api.v1.auth.dependencies import get_current_user
from src.api.v1.email_headers.schemas import (
    EmailHeaderListResponse,
    EmailHeaderResponse,
    EmailHeaderSubmit,
    HopSchema,
)
from src.core.domain.entities.user import User
from src.dependencies import get_db

router = APIRouter()


@router.post("/", response_model=EmailHeaderResponse, status_code=status.HTTP_201_CREATED)
async def analyze_email_headers(
    body: EmailHeaderSubmit,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EmailHeaderResponse:
    if not body.raw_headers.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="raw_headers must not be empty.")

    parser = EmailHeaderParser()
    parsed = parser.parse(body.raw_headers)

    hops_json = [
        {
            "index": h.index,
            "from_host": h.from_host,
            "by_host": h.by_host,
            "ip": h.ip,
            "timestamp": h.timestamp,
            "protocol": h.protocol,
            "delay_seconds": h.delay_seconds,
        }
        for h in parsed.hops
    ]

    model = EmailHeaderModel(
        id=uuid.uuid4(),
        created_at=datetime.now(timezone.utc),
        owner_id=current_user.id,
        subject=parsed.subject,
        sender_from=parsed.sender_from,
        sender_reply_to=parsed.sender_reply_to,
        originating_ip=parsed.originating_ip,
        originating_country=None,  # Geo-resolution deferred
        originating_city=None,
        spf_result=parsed.spf_result,
        dkim_result=parsed.dkim_result,
        dmarc_result=parsed.dmarc_result,
        is_spoofed=parsed.is_spoofed,
        hops=hops_json,
        raw_headers_summary=parsed.raw_headers_summary,
    )
    db.add(model)
    await db.flush()

    return _to_response(model)


@router.get("/", response_model=EmailHeaderListResponse)
async def list_email_checks(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> EmailHeaderListResponse:
    offset = (page - 1) * page_size
    total = (
        await db.execute(
            select(func.count()).select_from(EmailHeaderModel).where(EmailHeaderModel.owner_id == current_user.id)
        )
    ).scalar() or 0

    rows = list(
        (
            await db.execute(
                select(EmailHeaderModel)
                .where(EmailHeaderModel.owner_id == current_user.id)
                .order_by(EmailHeaderModel.created_at.desc())
                .limit(page_size)
                .offset(offset)
            )
        ).scalars().all()
    )

    return EmailHeaderListResponse(
        items=[_to_response(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get("/{check_id}", response_model=EmailHeaderResponse)
async def get_email_check(
    check_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EmailHeaderResponse:
    return _to_response(await _get_or_404(db, check_id, current_user.id))


@router.delete("/{check_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_email_check(
    check_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    model = await _get_or_404(db, check_id, current_user.id)
    await db.delete(model)
    await db.flush()


async def _get_or_404(db: AsyncSession, check_id: uuid.UUID, owner_id: uuid.UUID) -> EmailHeaderModel:
    result = await db.execute(
        select(EmailHeaderModel).where(
            EmailHeaderModel.id == check_id,
            EmailHeaderModel.owner_id == owner_id,
        )
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email header check not found.")
    return model


def _to_response(model: EmailHeaderModel) -> EmailHeaderResponse:
    hops = [HopSchema(**h) for h in (model.hops or [])]
    return EmailHeaderResponse(
        id=model.id,
        subject=model.subject,
        sender_from=model.sender_from,
        sender_reply_to=model.sender_reply_to,
        originating_ip=model.originating_ip,
        originating_country=model.originating_country,
        originating_city=model.originating_city,
        spf_result=model.spf_result,
        dkim_result=model.dkim_result,
        dmarc_result=model.dmarc_result,
        is_spoofed=model.is_spoofed,
        hops=hops,
        raw_headers_summary=model.raw_headers_summary or {},
        created_at=model.created_at,
    )
