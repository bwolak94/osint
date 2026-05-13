"""FastAPI router — Paste Monitor (paste site leak search)."""
from __future__ import annotations
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from src.adapters.paste_monitor.fetcher import search_pastes
from src.api.v1.auth.dependencies import get_current_user
from src.api.v1.paste_monitor.schemas import PasteMentionSchema, PasteMonitorRequest, PasteMonitorResponse
from src.core.domain.entities.user import User

log = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/", response_model=PasteMonitorResponse)
async def paste_monitor_search(
    body: PasteMonitorRequest,
    _: Annotated[User, Depends(get_current_user)],
) -> PasteMonitorResponse:
    q = body.query.strip()
    if not q:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="query must not be empty.")

    result = await search_pastes(q)
    return PasteMonitorResponse(
        query=result.query,
        total=result.total,
        mentions=[
            PasteMentionSchema(
                id=m.id,
                title=m.title,
                snippet=m.snippet,
                url=m.url,
                date=m.date,
                source=m.source,
                tags=m.tags,
            )
            for m in result.mentions
        ],
    )
