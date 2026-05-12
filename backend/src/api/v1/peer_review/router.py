"""Peer review workflow endpoints for pentest scans."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, List

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.pentest_extras_models import PeerReviewModel
from src.adapters.db.pentest_models import PentestScanModel
from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User
from src.dependencies import get_db

log = structlog.get_logger(__name__)
router = APIRouter(tags=["peer-review"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
UserDep = Annotated[User, Depends(get_current_user)]


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ReviewResponse(BaseModel):
    id: uuid.UUID
    scan_id: uuid.UUID
    reviewer_id: uuid.UUID | None
    status: str
    comments: str | None
    submitted_at: datetime | None
    reviewed_at: datetime | None

    model_config = {"from_attributes": True}


class ApproveReviewRequest(BaseModel):
    comments: str = ""


class RejectReviewRequest(BaseModel):
    comments: str
    changes_required: List[str] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_scan_or_404(scan_id: uuid.UUID, db: AsyncSession) -> PentestScanModel:
    stmt = select(PentestScanModel).where(PentestScanModel.id == scan_id)
    scan = (await db.execute(stmt)).scalar_one_or_none()
    if scan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found.")
    return scan


async def _get_review_for_scan(scan_id: uuid.UUID, db: AsyncSession) -> PeerReviewModel | None:
    stmt = (
        select(PeerReviewModel)
        .where(PeerReviewModel.scan_id == scan_id)
        .order_by(PeerReviewModel.submitted_at.desc().nulls_last())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


# ---------------------------------------------------------------------------
# POST /scans/{scan_id}/review/submit
# ---------------------------------------------------------------------------


@router.post(
    "/scans/{scan_id}/review/submit",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_scan_for_review(
    scan_id: uuid.UUID,
    current_user: UserDep,
    db: DbDep,
) -> ReviewResponse:
    """Submit a scan for peer review (creates a review record in 'pending' status)."""
    await _get_scan_or_404(scan_id, db)

    # Check if there is already a pending review
    existing = await _get_review_for_scan(scan_id, db)
    if existing and existing.status == "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This scan already has a pending review.",
        )

    review = PeerReviewModel(
        scan_id=scan_id,
        status="pending",
        submitted_at=datetime.now(timezone.utc),
    )
    db.add(review)
    await db.flush()

    log.info("review_submitted", scan_id=str(scan_id), review_id=str(review.id))
    return ReviewResponse.model_validate(review)


# ---------------------------------------------------------------------------
# GET /scans/{scan_id}/review
# ---------------------------------------------------------------------------


@router.get("/scans/{scan_id}/review", response_model=ReviewResponse)
async def get_review_status(
    scan_id: uuid.UUID,
    current_user: UserDep,
    db: DbDep,
) -> ReviewResponse:
    """Get the latest peer review record for a scan."""
    await _get_scan_or_404(scan_id, db)

    review = await _get_review_for_scan(scan_id, db)
    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No review found for this scan.",
        )
    return ReviewResponse.model_validate(review)


# ---------------------------------------------------------------------------
# POST /scans/{scan_id}/review/approve
# ---------------------------------------------------------------------------


@router.post("/scans/{scan_id}/review/approve", response_model=ReviewResponse)
async def approve_review(
    scan_id: uuid.UUID,
    request: ApproveReviewRequest,
    current_user: UserDep,
    db: DbDep,
) -> ReviewResponse:
    """Approve a pending peer review."""
    await _get_scan_or_404(scan_id, db)

    review = await _get_review_for_scan(scan_id, db)
    if review is None or review.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No pending review found for this scan.",
        )

    review.status = "approved"
    review.reviewer_id = current_user.id
    review.comments = request.comments or None
    review.reviewed_at = datetime.now(timezone.utc)
    await db.flush()

    log.info("review_approved", scan_id=str(scan_id), reviewer_id=str(current_user.id))
    return ReviewResponse.model_validate(review)


# ---------------------------------------------------------------------------
# POST /scans/{scan_id}/review/reject
# ---------------------------------------------------------------------------


@router.post("/scans/{scan_id}/review/reject", response_model=ReviewResponse)
async def reject_review(
    scan_id: uuid.UUID,
    request: RejectReviewRequest,
    current_user: UserDep,
    db: DbDep,
) -> ReviewResponse:
    """Reject a pending peer review with required changes."""
    await _get_scan_or_404(scan_id, db)

    review = await _get_review_for_scan(scan_id, db)
    if review is None or review.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No pending review found for this scan.",
        )

    changes_summary = (
        "\n\nRequired changes:\n" + "\n".join(f"- {c}" for c in request.changes_required)
        if request.changes_required
        else ""
    )

    review.status = "rejected"
    review.reviewer_id = current_user.id
    review.comments = request.comments + changes_summary
    review.reviewed_at = datetime.now(timezone.utc)
    await db.flush()

    log.info("review_rejected", scan_id=str(scan_id), reviewer_id=str(current_user.id))
    return ReviewResponse.model_validate(review)


# ---------------------------------------------------------------------------
# GET /reviews/pending
# ---------------------------------------------------------------------------


@router.get("/reviews/pending", response_model=List[ReviewResponse])
async def list_pending_reviews(
    current_user: UserDep,
    db: DbDep,
) -> List[ReviewResponse]:
    """List all pending peer reviews (for reviewers)."""
    stmt = (
        select(PeerReviewModel)
        .where(PeerReviewModel.status == "pending")
        .order_by(PeerReviewModel.submitted_at.asc())
    )
    reviews = (await db.execute(stmt)).scalars().all()
    return [ReviewResponse.model_validate(r) for r in reviews]
