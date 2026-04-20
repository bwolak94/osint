"""FastAPI router for Document Metadata Extractor module.

Endpoints:
  POST   /api/v1/doc-metadata/      — Upload a document and extract metadata
  GET    /api/v1/doc-metadata/      — Paginated history
  GET    /api/v1/doc-metadata/{id}  — Single record
  DELETE /api/v1/doc-metadata/{id}  — Delete record (204)
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.doc_metadata_models import DocMetadataModel
from src.adapters.doc_metadata.extractor import DocumentMetadataExtractor
from src.api.v1.auth.dependencies import get_current_user
from src.api.v1.doc_metadata.schemas import DocMetadataListResponse, DocMetadataResponse
from src.core.domain.entities.user import User
from src.dependencies import get_db

router = APIRouter()

_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

_ALLOWED_MIME_TYPES = frozenset(
    {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/msword",
        "application/vnd.ms-excel",
        "application/vnd.ms-powerpoint",
        "application/vnd.oasis.opendocument.text",
    }
)

_ALLOWED_EXTENSIONS = frozenset({".pdf", ".docx", ".xlsx", ".pptx", ".doc", ".xls", ".ppt", ".odt"})


@router.post("/", response_model=DocMetadataResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
) -> DocMetadataResponse:
    file_bytes = await file.read()

    if len(file_bytes) > _MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum allowed size is {_MAX_FILE_SIZE // (1024 * 1024)} MB.",
        )

    extractor = DocumentMetadataExtractor()
    extracted = extractor.extract(file_bytes, file.filename or "upload")

    lower_name = (file.filename or "").lower()
    ext_ok = any(lower_name.endswith(ext) for ext in _ALLOWED_EXTENSIONS)
    if not ext_ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Allowed: PDF, DOCX, XLSX, PPTX, DOC, XLS, PPT, ODT.",
        )

    model = DocMetadataModel(
        id=uuid.uuid4(),
        created_at=datetime.now(timezone.utc),
        owner_id=current_user.id,
        filename=extracted.filename,
        file_hash=extracted.file_hash,
        file_size=extracted.file_size,
        mime_type=extracted.mime_type,
        doc_format=extracted.doc_format,
        author=extracted.author,
        creator_tool=extracted.creator_tool,
        company=extracted.company,
        last_modified_by=extracted.last_modified_by,
        created_at_doc=extracted.created_at_doc,
        modified_at_doc=extracted.modified_at_doc,
        revision_count=extracted.revision_count,
        has_macros=extracted.has_macros,
        has_hidden_content=extracted.has_hidden_content,
        has_tracked_changes=extracted.has_tracked_changes,
        gps_lat=extracted.gps_lat,
        gps_lon=extracted.gps_lon,
        raw_metadata=extracted.raw_metadata,
        embedded_files=extracted.embedded_files,
    )
    db.add(model)
    await db.flush()

    return _to_response(model)


@router.get("/", response_model=DocMetadataListResponse)
async def list_doc_checks(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> DocMetadataListResponse:
    offset = (page - 1) * page_size
    total = (
        await db.execute(
            select(func.count()).select_from(DocMetadataModel).where(DocMetadataModel.owner_id == current_user.id)
        )
    ).scalar() or 0

    rows = list(
        (
            await db.execute(
                select(DocMetadataModel)
                .where(DocMetadataModel.owner_id == current_user.id)
                .order_by(DocMetadataModel.created_at.desc())
                .limit(page_size)
                .offset(offset)
            )
        ).scalars().all()
    )

    return DocMetadataListResponse(
        items=[_to_response(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get("/{check_id}", response_model=DocMetadataResponse)
async def get_doc_check(
    check_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DocMetadataResponse:
    return _to_response(await _get_or_404(db, check_id, current_user.id))


@router.delete("/{check_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_doc_check(
    check_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    model = await _get_or_404(db, check_id, current_user.id)
    await db.delete(model)
    await db.flush()


async def _get_or_404(db: AsyncSession, check_id: uuid.UUID, owner_id: uuid.UUID) -> DocMetadataModel:
    result = await db.execute(
        select(DocMetadataModel).where(
            DocMetadataModel.id == check_id,
            DocMetadataModel.owner_id == owner_id,
        )
    )
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document check not found.")
    return model


def _to_response(model: DocMetadataModel) -> DocMetadataResponse:
    return DocMetadataResponse(
        id=model.id,
        filename=model.filename,
        file_hash=model.file_hash,
        file_size=model.file_size,
        mime_type=model.mime_type,
        doc_format=model.doc_format,
        author=model.author,
        creator_tool=model.creator_tool,
        company=model.company,
        last_modified_by=model.last_modified_by,
        created_at_doc=model.created_at_doc,
        modified_at_doc=model.modified_at_doc,
        revision_count=model.revision_count,
        has_macros=model.has_macros,
        has_hidden_content=model.has_hidden_content,
        has_tracked_changes=model.has_tracked_changes,
        gps_lat=model.gps_lat,
        gps_lon=model.gps_lon,
        raw_metadata=model.raw_metadata or {},
        embedded_files=model.embedded_files or [],
        created_at=model.created_at,
    )
