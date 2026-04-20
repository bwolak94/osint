"""Global search across investigations and scan results."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.models import InvestigationModel, ScanResultModel
from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User
from src.dependencies import get_db

router = APIRouter()


class SearchResult(BaseModel):
    type: str  # "investigation" or "scan_result"
    id: str
    title: str
    snippet: str
    investigation_id: str | None = None


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    total: int


@router.get("/search", response_model=SearchResponse)
async def global_search(
    q: str = Query(..., min_length=2, max_length=200),
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> SearchResponse:
    """Search across investigations and scan results."""
    results: list[SearchResult] = []
    pattern = f"%{q}%"

    # Search investigations
    inv_stmt = (
        select(InvestigationModel)
        .where(
            InvestigationModel.owner_id == current_user.id,
            or_(
                InvestigationModel.title.ilike(pattern),
                InvestigationModel.description.ilike(pattern),
            ),
        )
        .limit(10)
    )
    inv_result = await db.execute(inv_stmt)
    for inv in inv_result.scalars().all():
        results.append(SearchResult(
            type="investigation",
            id=str(inv.id),
            title=inv.title,
            snippet=inv.description[:100] if inv.description else "",
        ))

    # Search scan results by input value or scanner name
    scan_stmt = (
        select(ScanResultModel)
        .join(InvestigationModel, ScanResultModel.investigation_id == InvestigationModel.id)
        .where(
            InvestigationModel.owner_id == current_user.id,
            or_(
                ScanResultModel.input_value.ilike(pattern),
                ScanResultModel.scanner_name.ilike(pattern),
            ),
        )
        .limit(10)
    )
    scan_result = await db.execute(scan_stmt)
    for sr in scan_result.scalars().all():
        results.append(SearchResult(
            type="scan_result",
            id=str(sr.id),
            title=f"{sr.scanner_name}: {sr.input_value}",
            snippet=f"Status: {sr.status}, Findings: {len(sr.extracted_identifiers or [])}",
            investigation_id=str(sr.investigation_id),
        ))

    return SearchResponse(query=q, results=results, total=len(results))
