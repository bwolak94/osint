"""CRUD and lifecycle router for investigations."""

import asyncio
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi import Query as QueryParam
from fastapi.responses import JSONResponse
from starlette.responses import StreamingResponse
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
    # Filter out internal tags from the public response
    public_tags = sorted(t for t in investigation.tags if not t.startswith("__"))
    # Extract schedule cron from internal tags
    schedule_cron = None
    for t in investigation.tags:
        if t.startswith("__schedule:"):
            schedule_cron = t.removeprefix("__schedule:")
            break
    return InvestigationResponse(
        id=investigation.id,
        title=investigation.title,
        description=investigation.description,
        status=investigation.status.value,
        owner_id=investigation.owner_id,
        seed_inputs=[_seed_domain_to_schema(s) for s in investigation.seed_inputs],
        tags=public_tags,
        scan_progress=ScanProgressSchema(),
        schedule_cron=schedule_cron,
        next_run_at=None,
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
    """Fetch an investigation and verify the current user owns it or has shared access."""
    investigation = await repo.get_by_id(investigation_id)
    if investigation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Investigation not found",
        )
    # Allow access if the user is the owner or is in the shared_with list
    if investigation.owner_id != user.id and str(user.id) not in getattr(investigation, "shared_with", []):
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
    from src.adapters.scanners.registry import get_default_registry
    from src.config import get_settings
    from src.core.domain.entities.types import ScanInputType

    settings = get_settings()
    registry = get_default_registry()

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

        # Check if investigation was paused before starting this seed
        async with async_session_factory() as check_session:
            from src.adapters.db.models import InvestigationModel
            inv_model = await check_session.get(InvestigationModel, investigation_id)
            if inv_model and inv_model.status != "running":
                log.info("Investigation paused/stopped, aborting scan", investigation_id=str(investigation_id))
                break

        # Publish progress before launching concurrent scans
        scanner_count = max(len(scanners), 1)
        if redis:
            try:
                await redis.publish(channel, json.dumps({
                    "type": "progress",
                    "completed": completed,
                    "total": total * scanner_count,
                    "percentage": round(completed / max(total * scanner_count, 1) * 100, 1),
                    "current_scanner": ",".join(s.scanner_name for s in scanners),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }))
            except Exception:
                pass

        # Run all scanners for this seed concurrently
        async def _run_single_scan(scanner, seed_value, scan_input_type, inv_id):
            return await scanner.scan(seed_value, scan_input_type, investigation_id=inv_id)

        tasks = [
            _run_single_scan(s, seed.value, input_type, investigation_id)
            for s in scanners
        ]
        scan_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results and save to DB
        for scanner, result in zip(scanners, scan_results):
            if isinstance(result, Exception):
                log.warning("Scanner failed", scanner=scanner.scanner_name, error=str(result))
                completed += 1
                continue

            try:
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
                log.warning("Failed to save scan result", scanner=scanner.scanner_name, error=str(exc))

            completed += 1

    # Auto-pivot: scan newly discovered identifiers (depth 2)
    if not aborted:
        new_seeds: set[tuple[str, str]] = set()
        original_values = {s.value for s in seed_inputs}
        async with async_session_factory() as session:
            pivot_scan_repo = SqlAlchemyScanResultRepository(session)
            all_results = await pivot_scan_repo.get_by_investigation(investigation_id)
            for r in all_results:
                for ident in (r.extracted_identifiers or []):
                    if ":" in ident:
                        kind, val = ident.split(":", 1)
                        if kind == "email" and val not in original_values:
                            new_seeds.add(("email", val))
                        elif kind == "username" and val not in original_values:
                            new_seeds.add(("username", val))

        if new_seeds and len(new_seeds) <= 5:
            log.info("Auto-pivot: scanning discovered identifiers", count=len(new_seeds), investigation_id=str(investigation_id))
            for seed_type, seed_value in new_seeds:
                input_type = ScanInputType(seed_type)
                scanners = registry.get_for_input_type(input_type)
                if enabled_scanners is not None:
                    scanners = [s for s in scanners if s.scanner_name in enabled_scanners]
                for scanner in scanners:
                    try:
                        result = await scanner.scan(seed_value, input_type, investigation_id=investigation_id)
                        async with async_session_factory() as save_session:
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
                            save_session.add(model)
                            await save_session.commit()
                        completed += 1
                    except Exception:
                        pass

    # Run entity resolution
    try:
        from src.adapters.entity_resolution.resolver import SimpleEntityResolver
        resolver = SimpleEntityResolver()

        async with async_session_factory() as resolve_session:
            scan_repo_resolve = SqlAlchemyScanResultRepository(resolve_session)
            all_results = await scan_repo_resolve.get_by_investigation(investigation_id)
            records = [{"extracted_identifiers": r.extracted_identifiers or [], **r.raw_data} for r in all_results if r.raw_data]
            clusters = resolver.cluster_records(records)
            log.info("Entity resolution complete", investigation_id=str(investigation_id), clusters=len(clusters))
    except Exception as exc:
        log.warning("Entity resolution failed", error=str(exc))

    # Mark investigation as completed
    async with async_session_factory() as session:
        from src.adapters.db.models import InvestigationModel
        model = await session.get(InvestigationModel, investigation_id)
        if model and model.status == "running":
            model.status = "completed"
            model.completed_at = datetime.now(timezone.utc)
            await session.commit()

    # TODO: Send email notification to user when investigation completes
    # await notification_service.send_investigation_complete(investigation_id, user_email)
    log.info("Investigation completed — notification would be sent here", investigation_id=str(investigation_id))

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

    # Use cursor-based pagination
    investigations, has_next = await repo.list_by_owner_cursor(
        current_user.id,
        cursor=cursor,
        limit=limit,
    )

    page = investigations

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
    updated = await repo.save(updated)
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

    await repo.save(archived)


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

    saved = await repo.save(paused)
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

    saved = await repo.save(running)
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

    # Query scan results from DB for real progress data
    scan_repo = SqlAlchemyScanResultRepository(db)
    results = await scan_repo.get_by_investigation(investigation_id)

    total = len(results)
    failed = sum(1 for r in results if r.status.value == "failed")
    completed = sum(1 for r in results if r.status.value in ("success", "failed"))
    percentage = round(completed / total * 100, 1) if total > 0 else 0.0

    return ScanProgressSchema(
        total_tasks=total,
        completed_tasks=completed,
        failed_tasks=failed,
        percentage=percentage,
    )


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


@router.post("/{investigation_id}/export")
async def export_investigation(
    investigation_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    format: str = QueryParam(default="json", regex="^(json|csv)$"),
):
    """Export investigation data as JSON or CSV."""
    repo = SqlAlchemyInvestigationRepository(db)
    investigation = await _get_owned_investigation(investigation_id, current_user, repo)

    scan_repo = SqlAlchemyScanResultRepository(db)
    results = await scan_repo.get_by_investigation(investigation_id)

    # CSV export format
    if format == "csv":
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Scanner", "Input", "Status", "Findings", "Duration (ms)", "Created At"])
        for r in results:
            writer.writerow([r.scanner_name, r.input_value, r.status.value, len(r.extracted_identifiers), r.duration_ms, r.created_at.isoformat()])

        return StreamingResponse(
            io.BytesIO(output.getvalue().encode()),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="investigation-{investigation_id}.csv"'},
        )

    # Default JSON export format
    export_data = {
        "investigation": {
            "id": str(investigation.id),
            "title": investigation.title,
            "description": investigation.description,
            "status": investigation.status.value,
            "created_at": investigation.created_at.isoformat(),
            "updated_at": investigation.updated_at.isoformat(),
            "seed_inputs": [{"type": s.input_type.value, "value": s.value} for s in investigation.seed_inputs],
            "tags": sorted(t for t in investigation.tags if not t.startswith("__")),
        },
        "scan_results": [
            {
                "scanner": r.scanner_name,
                "input": r.input_value,
                "status": r.status.value,
                "findings_count": len(r.extracted_identifiers),
                "duration_ms": r.duration_ms,
                "raw_data": r.raw_data or {},
                "created_at": r.created_at.isoformat(),
            }
            for r in results
        ],
        "exported_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    }

    return JSONResponse(
        content=export_data,
        headers={
            "Content-Disposition": f'attachment; filename="investigation-{investigation_id}.json"',
        },
    )


@router.get("/{investigation_id}/export/stix")
async def export_stix(
    investigation_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Export investigation data in STIX 2.1 format (simplified)."""
    inv_repo = SqlAlchemyInvestigationRepository(db)
    investigation = await inv_repo.get_by_id(investigation_id)
    if not investigation or investigation.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Investigation not found")

    scan_repo = SqlAlchemyScanResultRepository(db)
    results = await scan_repo.get_by_investigation(investigation_id)

    # Build simplified STIX bundle
    objects = []
    for r in results:
        if not r.raw_data or r.raw_data.get("_stub"):
            continue

        # Map scan results to STIX observed-data
        obj = {
            "type": "observed-data",
            "id": f"observed-data--{r.id}",
            "created": r.created_at.isoformat() + "Z" if r.created_at else "",
            "first_observed": r.created_at.isoformat() + "Z" if r.created_at else "",
            "last_observed": r.created_at.isoformat() + "Z" if r.created_at else "",
            "number_observed": 1,
            "objects": {
                "0": {
                    "type": "x-osint-scan-result",
                    "scanner": r.scanner_name,
                    "input": r.input_value,
                    "data": r.raw_data,
                }
            },
        }
        objects.append(obj)

    bundle = {
        "type": "bundle",
        "id": f"bundle--{investigation_id}",
        "objects": objects,
    }
    return bundle


@router.post("/{investigation_id}/schedule")
async def schedule_investigation(
    investigation_id: UUID,
    body: dict,  # {"cron": "0 0 * * 1"}
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Schedule recurring scans for an investigation."""
    # Store cron in tags as __schedule:cron_expression
    repo = SqlAlchemyInvestigationRepository(db)
    inv = await _get_owned_investigation(investigation_id, current_user, repo)
    cron = body.get("cron", "")
    tags = set(inv.tags)
    # Remove old schedule
    tags = {t for t in tags if not t.startswith("__schedule:")}
    if cron:
        tags.add(f"__schedule:{cron}")
    from dataclasses import replace
    updated = replace(inv, tags=frozenset(tags))
    await repo.save(updated)
    return {"status": "scheduled", "cron": cron}


@router.post("/admin/cleanup", tags=["admin"])
async def cleanup_old_investigations(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    retention_days: int = Query(default=90, ge=1, le=365),
) -> dict:
    """Delete investigations older than retention_days. Admin only."""
    if current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

    from sqlalchemy import delete
    from src.adapters.db.models import InvestigationModel

    stmt = delete(InvestigationModel).where(
        InvestigationModel.created_at < cutoff,
        InvestigationModel.status.in_(["completed", "archived"]),
    )
    result = await db.execute(stmt)
    await db.flush()

    return {"deleted": result.rowcount, "cutoff_date": cutoff.isoformat()}
