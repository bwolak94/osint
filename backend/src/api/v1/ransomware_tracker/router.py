"""FastAPI router — Ransomware Tracker via ransomware.live API."""
from __future__ import annotations
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from src.adapters.ransomware_tracker.fetcher import search_ransomware
from src.api.v1.auth.dependencies import get_current_user
from src.api.v1.ransomware_tracker.schemas import (
    RansomwareGroupSchema, RansomwareTrackerRequest, RansomwareTrackerResponse, RansomwareVictimSchema,
)
from src.core.domain.entities.user import User

log = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/", response_model=RansomwareTrackerResponse)
async def ransomware_tracker_search(
    body: RansomwareTrackerRequest,
    _: Annotated[User, Depends(get_current_user)],
) -> RansomwareTrackerResponse:
    q = body.query.strip()
    if not q:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="query must not be empty.")

    report = await search_ransomware(q)
    group = None
    if report.group_info:
        g = report.group_info
        # locations may be dicts from the API — coerce to strings
        locs = []
        for loc in g.locations:
            if isinstance(loc, dict):
                locs.append(loc.get("fqdn") or loc.get("title") or str(loc))
            else:
                locs.append(str(loc))
        group = RansomwareGroupSchema(
            name=g.name,
            description=g.description,
            locations=locs,
            profile_url=g.profile_url,
        )
    return RansomwareTrackerResponse(
        query=report.query,
        total_victims=report.total_victims,
        victims=[
            RansomwareVictimSchema(
                victim=v.victim,
                group=v.group,
                country=v.country,
                activity=v.activity,
                discovered=v.discovered,
                description=v.description,
                url=v.url,
                tags=v.tags,
            )
            for v in report.victims
        ],
        group_info=group,
    )
