"""CRUD router for investigations."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.investigations.schemas import (
    InvestigationCreate,
    InvestigationResponse,
    InvestigationUpdate,
)
from src.adapters.db.repositories import SqlAlchemyInvestigationRepository
from src.core.domain.entities.investigation import Investigation
from src.core.domain.events.base import DomainEvent
from src.core.use_cases.create_investigation import CreateInvestigation, CreateInvestigationInput
from src.dependencies import get_current_user, get_db

router = APIRouter()


async def _noop_publish(event: DomainEvent) -> None:
    """No-op event publisher (replace with real implementation)."""
    pass


@router.get("/", response_model=list[InvestigationResponse])
async def list_investigations(
    user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    offset: int = 0,
    limit: int = 50,
) -> list[InvestigationResponse]:
    """List investigations for the current user."""
    repo = SqlAlchemyInvestigationRepository(db)
    investigations = await repo.list_by_owner(UUID(user["user_id"]), offset=offset, limit=limit)
    return [InvestigationResponse.model_validate(inv, from_attributes=True) for inv in investigations]


@router.post("/", response_model=InvestigationResponse, status_code=status.HTTP_201_CREATED)
async def create_investigation(
    body: InvestigationCreate,
    user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InvestigationResponse:
    """Create a new investigation."""
    repo = SqlAlchemyInvestigationRepository(db)
    use_case = CreateInvestigation(repo=repo, publish=_noop_publish)
    investigation = await use_case.execute(
        CreateInvestigationInput(
            title=body.title,
            description=body.description,
            owner_id=UUID(user["user_id"]),
        )
    )
    return InvestigationResponse.model_validate(investigation, from_attributes=True)


@router.get("/{investigation_id}", response_model=InvestigationResponse)
async def get_investigation(
    investigation_id: UUID,
    user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InvestigationResponse:
    """Retrieve a single investigation by ID."""
    repo = SqlAlchemyInvestigationRepository(db)
    investigation = await repo.get_by_id(investigation_id)
    if investigation is None or investigation.owner_id != UUID(user["user_id"]):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investigation not found")
    return InvestigationResponse.model_validate(investigation, from_attributes=True)


@router.put("/{investigation_id}", response_model=InvestigationResponse)
async def update_investigation(
    investigation_id: UUID,
    body: InvestigationUpdate,
    user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InvestigationResponse:
    """Update an existing investigation."""
    repo = SqlAlchemyInvestigationRepository(db)
    investigation = await repo.get_by_id(investigation_id)
    if investigation is None or investigation.owner_id != UUID(user["user_id"]):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investigation not found")

    if body.title is not None:
        investigation.title = body.title
    if body.description is not None:
        investigation.description = body.description
    if body.status is not None:
        investigation.status = body.status

    updated = await repo.update(investigation)
    return InvestigationResponse.model_validate(updated, from_attributes=True)


@router.delete("/{investigation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_investigation(
    investigation_id: UUID,
    user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete an investigation."""
    repo = SqlAlchemyInvestigationRepository(db)
    investigation = await repo.get_by_id(investigation_id)
    if investigation is None or investigation.owner_id != UUID(user["user_id"]):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investigation not found")
    await repo.delete(investigation_id)
