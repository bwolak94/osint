"""CRUD and lifecycle router for investigations."""

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.repositories import SqlAlchemyInvestigationRepository
from src.adapters.db.scan_result_repository import SqlAlchemyScanResultRepository
from src.api.v1.auth.dependencies import get_current_user
from src.api.v1.investigations.schemas import (
    CreateInvestigationRequest,
    ExportRequest,
    InvestigationListResponse,
    InvestigationResponse,
    InvestigationResultsResponse,
    MessageResponse,
    ScanProgressSchema,
    ScanResultResponse,
    SeedInputSchema,
    UpdateInvestigationRequest,
)
from src.core.domain.entities.investigation import Investigation
from src.core.domain.entities.types import ScanInputType, SeedInput
from src.core.domain.entities.user import User
from src.core.domain.events.base import DomainEvent
from src.core.use_cases.create_investigation import (
    CreateInvestigation,
    CreateInvestigationInput,
)
from src.core.use_cases.investigations.run_investigation import (
    RunInvestigationCommand,
    RunInvestigationUseCase,
)
from src.dependencies import get_db

log = structlog.get_logger()

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _noop_publish(event: DomainEvent) -> None:
    """No-op event publisher used until a real broker is wired in."""


class _NoopEventPublisher:
    """Minimal event publisher that satisfies the IEventPublisher protocol."""

    async def publish(self, event: DomainEvent) -> None:
        pass

    async def publish_many(self, events: list[DomainEvent]) -> None:
        pass


def _seed_schema_to_domain(schema: SeedInputSchema) -> SeedInput:
    """Convert an API-level SeedInputSchema to the domain SeedInput type."""
    return SeedInput(value=schema.value, input_type=ScanInputType(schema.type))


def _seed_domain_to_schema(seed: SeedInput) -> SeedInputSchema:
    """Convert a domain SeedInput to the API-level SeedInputSchema."""
    return SeedInputSchema(type=seed.input_type.value, value=seed.value)


def _build_response(investigation: Investigation) -> InvestigationResponse:
    """Map a domain Investigation entity to the API response schema."""
    return InvestigationResponse(
        id=investigation.id,
        title=investigation.title,
        description=investigation.description,
        status=investigation.status.value,
        owner_id=investigation.owner_id,
        seed_inputs=[_seed_domain_to_schema(s) for s in investigation.seed_inputs],
        tags=sorted(investigation.tags),
        scan_progress=ScanProgressSchema(),
        created_at=investigation.created_at,
        updated_at=investigation.updated_at,
        completed_at=investigation.completed_at,
    )


async def _get_owned_investigation(
    investigation_id: UUID,
    user: User,
    repo: SqlAlchemyInvestigationRepository,
) -> Investigation:
    """Fetch an investigation and verify the current user owns it."""
    investigation = await repo.get_by_id(investigation_id)
    if investigation is None or investigation.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Investigation not found",
        )
    return investigation


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/",
    response_model=InvestigationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_investigation(
    body: CreateInvestigationRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InvestigationResponse:
    """Create a new investigation with seed inputs."""
    repo = SqlAlchemyInvestigationRepository(db)
    use_case = CreateInvestigation(repo=repo, publish=_noop_publish)

    seeds = [_seed_schema_to_domain(s) for s in body.seed_inputs]
    investigation = await use_case.execute(
        CreateInvestigationInput(
            title=body.title,
            description=body.description,
            owner_id=current_user.id,
            seed_inputs=seeds,
            tags=frozenset(body.tags),
        )
    )

    return _build_response(investigation)


@router.get("/", response_model=InvestigationListResponse)
async def list_investigations(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    cursor: UUID | None = Query(default=None, description="Last seen investigation ID for cursor pagination"),
    limit: int = Query(default=20, ge=1, le=100),
) -> InvestigationListResponse:
    """List investigations with cursor-based pagination."""
    repo = SqlAlchemyInvestigationRepository(db)

    # Fetch limit+1 to determine if there is a next page
    investigations = await repo.list_by_owner(
        current_user.id,
        offset=0,
        limit=limit + 1,
    )

    has_next = len(investigations) > limit
    page = investigations[:limit]

    next_cursor: str | None = None
    if has_next and page:
        next_cursor = str(page[-1].id)

    return InvestigationListResponse(
        items=[_build_response(inv) for inv in page],
        total=len(page),
        has_next=has_next,
        next_cursor=next_cursor,
    )


@router.get("/{investigation_id}", response_model=InvestigationResponse)
async def get_investigation(
    investigation_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InvestigationResponse:
    """Retrieve a single investigation by ID."""
    repo = SqlAlchemyInvestigationRepository(db)
    investigation = await _get_owned_investigation(investigation_id, current_user, repo)
    return _build_response(investigation)


@router.patch("/{investigation_id}", response_model=InvestigationResponse)
async def update_investigation(
    investigation_id: UUID,
    body: UpdateInvestigationRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InvestigationResponse:
    """Update title, description, or tags of an investigation."""
    repo = SqlAlchemyInvestigationRepository(db)
    investigation = await _get_owned_investigation(investigation_id, current_user, repo)

    title = body.title if body.title is not None else investigation.title
    description = body.description if body.description is not None else investigation.description
    tags = frozenset(body.tags) if body.tags is not None else investigation.tags

    updated = Investigation(
        id=investigation.id,
        owner_id=investigation.owner_id,
        title=title,
        description=description,
        status=investigation.status,
        seed_inputs=investigation.seed_inputs,
        tags=tags,
        created_at=investigation.created_at,
        updated_at=investigation.updated_at,
        completed_at=investigation.completed_at,
    )
    updated = await repo.update(updated)
    return _build_response(updated)


@router.delete("/{investigation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_investigation(
    investigation_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Soft-delete (archive) an investigation."""
    repo = SqlAlchemyInvestigationRepository(db)
    investigation = await _get_owned_investigation(investigation_id, current_user, repo)

    try:
        archived = investigation.archive()
    except ValueError:
        # If not in COMPLETED state, fall back to hard delete for DRAFT/ARCHIVED
        if investigation.can_be_deleted_by(current_user):
            await repo.delete(investigation_id)
            return
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete investigation in status '{investigation.status.value}'",
        )

    await repo.update(archived)


@router.post("/{investigation_id}/start", response_model=InvestigationResponse)
async def start_investigation(
    investigation_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InvestigationResponse:
    """Start the scanning pipeline for an investigation."""
    repo = SqlAlchemyInvestigationRepository(db)
    investigation = await _get_owned_investigation(investigation_id, current_user, repo)

    try:
        running = investigation.mark_running()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    saved = await repo.update(running)

    # Dispatch the Celery scanning pipeline
    publisher = _NoopEventPublisher()
    use_case = RunInvestigationUseCase(
        investigation_repo=repo,
        event_publisher=publisher,
    )
    try:
        await use_case.execute(RunInvestigationCommand(investigation_id=investigation_id))
    except Exception:
        await log.awarning(
            "Failed to dispatch investigation pipeline",
            investigation_id=str(investigation_id),
        )

    return _build_response(saved)


@router.post("/{investigation_id}/pause", response_model=InvestigationResponse)
async def pause_investigation(
    investigation_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InvestigationResponse:
    """Pause a running investigation."""
    repo = SqlAlchemyInvestigationRepository(db)
    investigation = await _get_owned_investigation(investigation_id, current_user, repo)

    try:
        paused = investigation.pause()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    saved = await repo.update(paused)
    return _build_response(saved)


@router.post("/{investigation_id}/resume", response_model=InvestigationResponse)
async def resume_investigation(
    investigation_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InvestigationResponse:
    """Resume a paused investigation."""
    repo = SqlAlchemyInvestigationRepository(db)
    investigation = await _get_owned_investigation(investigation_id, current_user, repo)

    try:
        running = investigation.mark_running()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    saved = await repo.update(running)
    return _build_response(saved)


@router.get("/{investigation_id}/status", response_model=ScanProgressSchema)
async def get_investigation_status(
    investigation_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ScanProgressSchema:
    """Polling fallback to check scan progress for an investigation."""
    repo = SqlAlchemyInvestigationRepository(db)
    await _get_owned_investigation(investigation_id, current_user, repo)

    # Real progress tracking will be delivered via WebSocket.
    # This endpoint returns a default for now.
    return ScanProgressSchema()


@router.get("/{investigation_id}/results", response_model=InvestigationResultsResponse)
async def get_investigation_results(
    investigation_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InvestigationResultsResponse:
    """Retrieve scan results for an investigation."""
    inv_repo = SqlAlchemyInvestigationRepository(db)
    await _get_owned_investigation(investigation_id, current_user, inv_repo)

    scan_repo = SqlAlchemyScanResultRepository(db)
    results = await scan_repo.get_by_investigation(investigation_id)

    scan_responses = [
        ScanResultResponse(
            id=r.id,
            scanner_name=r.scanner_name,
            input_value=r.input_value,
            status=r.status.value,
            findings_count=len(r.extracted_identifiers),
            duration_ms=r.duration_ms,
            created_at=r.created_at,
            error_message=r.error_message,
        )
        for r in results
    ]

    successful = sum(1 for r in results if r.is_successful())
    failed = sum(1 for r in results if r.status.value == "failed")

    return InvestigationResultsResponse(
        investigation_id=investigation_id,
        scan_results=scan_responses,
        total_scans=len(results),
        successful_scans=successful,
        failed_scans=failed,
    )


@router.post("/{investigation_id}/export", response_model=MessageResponse)
async def export_investigation(
    investigation_id: UUID,
    body: ExportRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    """Trigger an export of the investigation data (placeholder)."""
    repo = SqlAlchemyInvestigationRepository(db)
    await _get_owned_investigation(investigation_id, current_user, repo)

    return MessageResponse(
        message=f"Export in '{body.format}' format has been queued for investigation {investigation_id}.",
    )
