"""Finding library CRUD — pre-written vulnerability write-ups."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, List

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.pentest_extras_models import FindingLibraryModel
from src.adapters.db.pentest_models import PentestFindingModel
from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User
from src.dependencies import get_db

log = structlog.get_logger(__name__)
router = APIRouter(tags=["finding-library"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
UserDep = Annotated[User, Depends(get_current_user)]


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class FindingLibraryResponse(BaseModel):
    id: uuid.UUID
    title: str
    severity: str | None
    cwe: int | None
    wstg_id: str | None
    mitre_techniques: list[str] | None
    description: str
    remediation: str
    references: list
    tags: list[str] | None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CreateFindingLibraryRequest(BaseModel):
    title: str
    severity: str | None = None
    cwe: int | None = None
    wstg_id: str | None = None
    mitre_techniques: list[str] | None = None
    description: str
    remediation: str
    references: list = []
    tags: list[str] | None = None


class UpdateFindingLibraryRequest(BaseModel):
    title: str | None = None
    severity: str | None = None
    cwe: int | None = None
    wstg_id: str | None = None
    mitre_techniques: list[str] | None = None
    description: str | None = None
    remediation: str | None = None
    references: list | None = None
    tags: list[str] | None = None


class PaginatedLibraryResponse(BaseModel):
    items: List[FindingLibraryResponse]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _entry_or_404(entry: FindingLibraryModel | None) -> FindingLibraryModel:
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library entry not found.")
    return entry


def _to_response(m: FindingLibraryModel) -> FindingLibraryResponse:
    return FindingLibraryResponse(
        id=m.id,
        title=m.title,
        severity=m.severity,
        cwe=m.cwe,
        wstg_id=m.wstg_id,
        mitre_techniques=m.mitre_techniques,
        description=m.description,
        remediation=m.remediation,
        references=m.references or [],
        tags=m.tags,
        created_by=m.created_by,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


# ---------------------------------------------------------------------------
# GET /finding-library
# ---------------------------------------------------------------------------


@router.get("", response_model=PaginatedLibraryResponse)
async def list_library_entries(
    current_user: UserDep,
    db: DbDep,
    q: str | None = Query(default=None, description="Full-text search on title/description"),
    tag: str | None = Query(default=None, description="Filter by tag"),
    severity: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> PaginatedLibraryResponse:
    stmt = select(FindingLibraryModel).order_by(FindingLibraryModel.created_at.desc())

    if q is not None:
        pattern = f"%{q}%"
        stmt = stmt.where(
            or_(
                FindingLibraryModel.title.ilike(pattern),
                FindingLibraryModel.description.ilike(pattern),
            )
        )
    if tag is not None:
        stmt = stmt.where(FindingLibraryModel.tags.contains([tag]))
    if severity is not None:
        stmt = stmt.where(FindingLibraryModel.severity == severity)

    # Count total before pagination
    from sqlalchemy import func

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total: int = (await db.execute(count_stmt)).scalar_one()

    stmt = stmt.offset(offset).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()

    return PaginatedLibraryResponse(
        items=[_to_response(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# POST /finding-library
# ---------------------------------------------------------------------------


@router.post("", response_model=FindingLibraryResponse, status_code=status.HTTP_201_CREATED)
async def create_library_entry(
    request: CreateFindingLibraryRequest,
    current_user: UserDep,
    db: DbDep,
) -> FindingLibraryResponse:
    entry = FindingLibraryModel(
        id=uuid.uuid4(),
        title=request.title,
        severity=request.severity,
        cwe=request.cwe,
        wstg_id=request.wstg_id,
        mitre_techniques=request.mitre_techniques,
        description=request.description,
        remediation=request.remediation,
        references=request.references,
        tags=request.tags,
        created_by=current_user.id,
    )
    db.add(entry)
    await db.flush()
    await db.refresh(entry)
    log.info("finding_library_entry_created", entry_id=str(entry.id), user_id=str(current_user.id))
    return _to_response(entry)


# ---------------------------------------------------------------------------
# GET /finding-library/{id}
# ---------------------------------------------------------------------------


@router.get("/{entry_id}", response_model=FindingLibraryResponse)
async def get_library_entry(
    entry_id: uuid.UUID,
    current_user: UserDep,
    db: DbDep,
) -> FindingLibraryResponse:
    stmt = select(FindingLibraryModel).where(FindingLibraryModel.id == entry_id)
    entry = (await db.execute(stmt)).scalar_one_or_none()
    return _to_response(_entry_or_404(entry))


# ---------------------------------------------------------------------------
# PUT /finding-library/{id}
# ---------------------------------------------------------------------------


@router.put("/{entry_id}", response_model=FindingLibraryResponse)
async def update_library_entry(
    entry_id: uuid.UUID,
    request: UpdateFindingLibraryRequest,
    current_user: UserDep,
    db: DbDep,
) -> FindingLibraryResponse:
    stmt = select(FindingLibraryModel).where(FindingLibraryModel.id == entry_id)
    entry = (await db.execute(stmt)).scalar_one_or_none()
    _entry_or_404(entry)
    assert entry is not None

    if request.title is not None:
        entry.title = request.title
    if request.severity is not None:
        entry.severity = request.severity
    if request.cwe is not None:
        entry.cwe = request.cwe
    if request.wstg_id is not None:
        entry.wstg_id = request.wstg_id
    if request.mitre_techniques is not None:
        entry.mitre_techniques = request.mitre_techniques
    if request.description is not None:
        entry.description = request.description
    if request.remediation is not None:
        entry.remediation = request.remediation
    if request.references is not None:
        entry.references = request.references
    if request.tags is not None:
        entry.tags = request.tags

    await db.flush()
    await db.refresh(entry)
    log.info("finding_library_entry_updated", entry_id=str(entry_id), user_id=str(current_user.id))
    return _to_response(entry)


# ---------------------------------------------------------------------------
# DELETE /finding-library/{id}
# ---------------------------------------------------------------------------


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_library_entry(
    entry_id: uuid.UUID,
    current_user: UserDep,
    db: DbDep,
) -> None:
    stmt = select(FindingLibraryModel).where(FindingLibraryModel.id == entry_id)
    entry = (await db.execute(stmt)).scalar_one_or_none()
    _entry_or_404(entry)
    assert entry is not None
    await db.delete(entry)
    await db.flush()
    log.info("finding_library_entry_deleted", entry_id=str(entry_id), user_id=str(current_user.id))


# ---------------------------------------------------------------------------
# POST /finding-library/{id}/apply/{finding_id}
# ---------------------------------------------------------------------------


class ApplyLibraryResponse(BaseModel):
    finding_id: uuid.UUID
    library_entry_id: uuid.UUID
    applied_fields: list[str]


@router.post("/{entry_id}/apply/{finding_id}", response_model=ApplyLibraryResponse)
async def apply_library_entry_to_finding(
    entry_id: uuid.UUID,
    finding_id: uuid.UUID,
    current_user: UserDep,
    db: DbDep,
) -> ApplyLibraryResponse:
    """Copy description, remediation, WSTG ID, and MITRE techniques from a library entry to a live finding."""
    lib_stmt = select(FindingLibraryModel).where(FindingLibraryModel.id == entry_id)
    entry = (await db.execute(lib_stmt)).scalar_one_or_none()
    _entry_or_404(entry)
    assert entry is not None

    finding_stmt = select(PentestFindingModel).where(PentestFindingModel.id == finding_id)
    finding = (await db.execute(finding_stmt)).scalar_one_or_none()
    if finding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found.")

    applied_fields: list[str] = []

    finding.description = entry.description
    applied_fields.append("description")

    finding.remediation = entry.remediation
    applied_fields.append("remediation")

    if entry.wstg_id is not None:
        finding.wstg_id = entry.wstg_id
        applied_fields.append("wstg_id")

    if entry.mitre_techniques is not None:
        finding.mitre_techniques = entry.mitre_techniques
        applied_fields.append("mitre_techniques")

    if entry.cwe is not None:
        finding.cwe = entry.cwe
        applied_fields.append("cwe")

    await db.flush()
    log.info(
        "finding_library_entry_applied",
        entry_id=str(entry_id),
        finding_id=str(finding_id),
        user_id=str(current_user.id),
        applied_fields=applied_fields,
    )

    return ApplyLibraryResponse(
        finding_id=finding_id,
        library_entry_id=entry_id,
        applied_fields=applied_fields,
    )
