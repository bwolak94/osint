"""CRUD and lifecycle router for investigations."""

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.repositories import SqlAlchemyInvestigationRepository
from src.adapters.db.scan_result_repository import SqlAlchemyScanResultRepository
from src.api.v1.auth.dependencies import get_current_user
from src.api.v1.investigations.schemas import (
    CreateInvestigationRequest,
    ExportRequest,
    IdentityResponse,
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
    # Filter out internal __scanner: tags from the public response
    public_tags = sorted(t for t in investigation.tags if not t.startswith("__scanner:"))
    return InvestigationResponse(
        id=investigation.id,
        title=investigation.title,
        description=investigation.description,
        status=investigation.status.value,
        owner_id=investigation.owner_id,
        seed_inputs=[_seed_domain_to_schema(s) for s in investigation.seed_inputs],
        tags=public_tags,
        scan_progress=ScanProgressSchema(),
        created_at=investigation.created_at,
        updated_at=investigation.updated_at,
        completed_at=investigation.completed_at,
    )


def _extract_enabled_scanners(investigation: Investigation) -> list[str] | None:
    """Extract enabled scanner names from internal __scanner: tags.

    Returns None if no scanner tags are found (meaning all scanners should run).
    """
    scanners = [
        t.removeprefix("__scanner:")
        for t in investigation.tags
        if t.startswith("__scanner:")
    ]
    return scanners if scanners else None


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


async def _run_scans_background(
    investigation_id: UUID,
    seed_inputs: list,
    enabled_scanners: list[str] | None = None,
) -> None:
    """Run scanners for each seed input directly (no Celery required)."""
    import json
    from datetime import datetime, timezone
    from uuid import uuid4

    import redis.asyncio as aioredis

    from src.adapters.db.database import async_session_factory
    from src.adapters.db.models import ScanResultModel
    from src.adapters.scanners.registry import create_default_registry
    from src.config import get_settings
    from src.core.domain.entities.types import ScanInputType

    settings = get_settings()
    registry = create_default_registry()

    # Connect to Redis for progress publishing
    try:
        redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    except Exception:
        redis = None

    channel = f"investigation:{investigation_id}:progress"
    total = len(seed_inputs)
    completed = 0

    for seed in seed_inputs:
        input_type = ScanInputType(seed.input_type.value if hasattr(seed.input_type, "value") else seed.input_type)
        scanners = registry.get_for_input_type(input_type)

        # Filter to only enabled scanners if a selection was provided
        if enabled_scanners is not None:
            scanners = [s for s in scanners if s.scanner_name in enabled_scanners]

        for scanner in scanners:
            # Publish progress
            if redis:
                try:
                    await redis.publish(channel, json.dumps({
                        "type": "progress",
                        "completed": completed,
                        "total": total * max(len(scanners), 1),
                        "percentage": round(completed / max(total * max(len(scanners), 1), 1) * 100, 1),
                        "current_scanner": scanner.scanner_name,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }))
                except Exception:
                    pass

            # Run the scanner
            try:
                result = await scanner.scan(seed.value, input_type, investigation_id=investigation_id)

                # Save result to DB
                async with async_session_factory() as session:
                    model = ScanResultModel(
                        id=result.id,
                        investigation_id=investigation_id,
                        scanner_name=result.scanner_name,
                        input_value=result.input_value,
                        status=result.status,
                        raw_data=result.raw_data,
                        extracted_identifiers=result.extracted_identifiers,
                        duration_ms=result.duration_ms,
                        error_message=result.error_message,
                    )
                    session.add(model)
                    await session.commit()

                # Publish scan complete
                if redis:
                    try:
                        await redis.publish(channel, json.dumps({
                            "type": "scan_complete",
                            "scanner": scanner.scanner_name,
                            "findings_count": len(result.extracted_identifiers),
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }))
                    except Exception:
                        pass
            except Exception as exc:
                log.warning("Scanner failed", scanner=scanner.scanner_name, error=str(exc))

            completed += 1

    # Mark investigation as completed
    async with async_session_factory() as session:
        from src.adapters.db.models import InvestigationModel
        model = await session.get(InvestigationModel, investigation_id)
        if model and model.status == "running":
            model.status = "completed"
            model.completed_at = datetime.now(timezone.utc)
            await session.commit()

    # Publish completion
    if redis:
        try:
            await redis.publish(channel, json.dumps({
                "type": "investigation_complete",
                "summary": {"total_scans": completed},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }))
        except Exception:
            pass
        await redis.close()

    log.info("Background scan completed", investigation_id=str(investigation_id), scans=completed)


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

    # Store enabled_scanners in tags with a special prefix so the start
    # endpoint can retrieve them later without a DB schema change.
    tags = set(body.tags)
    if body.enabled_scanners is not None:
        for scanner_name in body.enabled_scanners:
            tags.add(f"__scanner:{scanner_name}")

    investigation = await use_case.execute(
        CreateInvestigationInput(
            title=body.title,
            description=body.description,
            owner_id=current_user.id,
            seed_inputs=seeds,
            tags=frozenset(tags),
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
    background_tasks: BackgroundTasks,
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

    saved = await repo.save(running)

    # Extract enabled scanners from internal tags (set during create)
    enabled_scanners = _extract_enabled_scanners(investigation)

    # Run scans in background (inline, no Celery needed)
    background_tasks.add_task(
        _run_scans_background, investigation_id, saved.seed_inputs, enabled_scanners
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
            raw_data=r.raw_data or {},
            extracted_identifiers=r.extracted_identifiers or [],
        )
        for r in results
    ]

    # Build identities from raw scan data
    identities: list[IdentityResponse] = []
    _internal_keys = {"raw_results", "_stub", "_extracted_identifiers", "extracted_identifiers"}
    for r in results:
        if not r.raw_data or r.raw_data.get("_stub"):
            continue
        cleaned_data = {k: v for k, v in r.raw_data.items() if k not in _internal_keys}

        # VAT / KRS / CEIDG results (have "found" flag)
        if r.raw_data.get("found") and r.raw_data.get("name"):
            identities.append(IdentityResponse(
                id=str(r.id),
                name=r.raw_data["name"],
                type="company" if r.raw_data.get("nip") else "person",
                confidence=0.9 if r.is_successful() else 0.5,
                data=cleaned_data,
                sources=[r.scanner_name],
            ))

        # Holehe results (email registration check)
        elif r.raw_data.get("registered_count", 0) > 0:
            services = r.raw_data.get("registered_on", [])
            identities.append(IdentityResponse(
                id=str(r.id),
                name=r.input_value,
                type="email_identity",
                confidence=0.8,
                data={
                    "email": r.input_value,
                    "registered_on": services,
                    "registered_count": len(services),
                    "partial_phone": r.raw_data.get("partial_phone"),
                    "backup_email": r.raw_data.get("backup_email"),
                },
                sources=[r.scanner_name],
            ))

        # Maigret results (username profile check)
        elif r.raw_data.get("claimed_count", 0) > 0:
            profiles = r.raw_data.get("claimed_profiles", [])
            identities.append(IdentityResponse(
                id=str(r.id),
                name=r.input_value,
                type="username_identity",
                confidence=0.7,
                data={
                    "username": r.input_value,
                    "claimed_profiles": profiles[:30],
                    "claimed_count": r.raw_data.get("claimed_count", 0),
                    "total_checked": r.raw_data.get("total_checked", 0),
                },
                sources=[r.scanner_name],
            ))

    successful = sum(1 for r in results if r.is_successful())
    failed = sum(1 for r in results if r.status.value == "failed")

    return InvestigationResultsResponse(
        investigation_id=investigation_id,
        scan_results=scan_responses,
        total_scans=len(results),
        successful_scans=successful,
        failed_scans=failed,
        identities=identities,
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
