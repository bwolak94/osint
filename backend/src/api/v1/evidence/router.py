"""Evidence management endpoints — upload, download, delete file attachments for findings."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.pentest_extras_models import EvidenceModel
from src.adapters.db.pentest_models import PentestFindingModel
from src.adapters.storage.minio_client import MinioStorageClient
from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User
from src.dependencies import get_db

log = structlog.get_logger(__name__)
router = APIRouter(tags=["evidence"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
UserDep = Annotated[User, Depends(get_current_user)]

EVIDENCE_BUCKET = "pentest-evidence"
PRESIGNED_EXPIRY_SECONDS = 600  # 10 minutes


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class EvidenceResponse(BaseModel):
    id: uuid.UUID
    finding_id: uuid.UUID
    scan_id: uuid.UUID | None
    type: str
    filename: str
    storage_ref: str | None
    content_type: str | None
    size_bytes: int | None
    description: str | None
    captured_at: datetime
    uploaded_by: uuid.UUID

    model_config = {"from_attributes": True}


class PresignedUrlResponse(BaseModel):
    url: str
    expires_in_seconds: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _evidence_or_404(evidence: EvidenceModel | None) -> EvidenceModel:
    if evidence is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found.")
    return evidence


def _to_response(m: EvidenceModel) -> EvidenceResponse:
    return EvidenceResponse(
        id=m.id,
        finding_id=m.finding_id,
        scan_id=m.scan_id,
        type=m.type,
        filename=m.filename,
        storage_ref=m.storage_ref,
        content_type=m.content_type,
        size_bytes=m.size_bytes,
        description=m.description,
        captured_at=m.captured_at,
        uploaded_by=m.uploaded_by,
    )


def _ensure_evidence_bucket(minio: MinioStorageClient) -> None:
    """Ensure the pentest-evidence bucket exists, create it if not."""
    if not minio._client.bucket_exists(EVIDENCE_BUCKET):
        minio._client.make_bucket(EVIDENCE_BUCKET)


# ---------------------------------------------------------------------------
# GET /findings/{finding_id}/evidence
# ---------------------------------------------------------------------------


@router.get("/findings/{finding_id}/evidence", response_model=list[EvidenceResponse])
async def list_evidence(
    finding_id: uuid.UUID,
    current_user: UserDep,
    db: DbDep,
) -> list[EvidenceResponse]:
    # Verify finding exists
    finding_stmt = select(PentestFindingModel).where(PentestFindingModel.id == finding_id)
    finding = (await db.execute(finding_stmt)).scalar_one_or_none()
    if finding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found.")

    stmt = (
        select(EvidenceModel)
        .where(EvidenceModel.finding_id == finding_id)
        .order_by(EvidenceModel.captured_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_response(r) for r in rows]


# ---------------------------------------------------------------------------
# POST /findings/{finding_id}/evidence  (multipart upload)
# ---------------------------------------------------------------------------


@router.post(
    "/findings/{finding_id}/evidence",
    response_model=EvidenceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_evidence(
    finding_id: uuid.UUID,
    current_user: UserDep,
    db: DbDep,
    file: UploadFile = File(...),
    type: str = Form(..., description="screenshot / http_log / terminal / file / poc"),
    description: str | None = Form(default=None),
) -> EvidenceResponse:
    # Verify finding exists
    finding_stmt = select(PentestFindingModel).where(PentestFindingModel.id == finding_id)
    finding = (await db.execute(finding_stmt)).scalar_one_or_none()
    if finding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found.")

    # Read file data
    file_data = await file.read()
    file_size = len(file_data)
    original_filename = file.filename or "upload"
    content_type = file.content_type or "application/octet-stream"

    # Build MinIO object key
    evidence_id = uuid.uuid4()
    object_name = f"{finding_id}/{evidence_id}_{original_filename}"

    try:
        minio = MinioStorageClient()
        _ensure_evidence_bucket(minio)
        minio._client.put_object(
            bucket_name=EVIDENCE_BUCKET,
            object_name=object_name,
            data=__import__("io").BytesIO(file_data),
            length=file_size,
            content_type=content_type,
        )
        storage_ref = object_name
    except Exception as exc:
        log.error("evidence_upload_minio_failed", error=str(exc), finding_id=str(finding_id))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Storage upload failed: {exc}",
        ) from exc

    evidence = EvidenceModel(
        id=evidence_id,
        finding_id=finding_id,
        scan_id=finding.scan_id,
        type=type,
        filename=original_filename,
        storage_ref=storage_ref,
        content_type=content_type,
        size_bytes=file_size,
        description=description,
        captured_at=datetime.now(timezone.utc),
        uploaded_by=current_user.id,
    )
    db.add(evidence)
    await db.flush()
    await db.refresh(evidence)

    log.info(
        "evidence_uploaded",
        evidence_id=str(evidence_id),
        finding_id=str(finding_id),
        filename=original_filename,
        user_id=str(current_user.id),
    )
    return _to_response(evidence)


# ---------------------------------------------------------------------------
# GET /evidence/{id}
# ---------------------------------------------------------------------------


@router.get("/evidence/{evidence_id}", response_model=EvidenceResponse)
async def get_evidence(
    evidence_id: uuid.UUID,
    current_user: UserDep,
    db: DbDep,
) -> EvidenceResponse:
    stmt = select(EvidenceModel).where(EvidenceModel.id == evidence_id)
    evidence = (await db.execute(stmt)).scalar_one_or_none()
    return _to_response(_evidence_or_404(evidence))


# ---------------------------------------------------------------------------
# DELETE /evidence/{id}
# ---------------------------------------------------------------------------


@router.delete("/evidence/{evidence_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_evidence(
    evidence_id: uuid.UUID,
    current_user: UserDep,
    db: DbDep,
) -> None:
    stmt = select(EvidenceModel).where(EvidenceModel.id == evidence_id)
    evidence = (await db.execute(stmt)).scalar_one_or_none()
    _evidence_or_404(evidence)
    assert evidence is not None

    # Remove from MinIO if a storage ref exists
    if evidence.storage_ref:
        try:
            minio = MinioStorageClient()
            minio._client.remove_object(EVIDENCE_BUCKET, evidence.storage_ref)
        except Exception as exc:
            log.warning(
                "evidence_delete_minio_failed",
                evidence_id=str(evidence_id),
                storage_ref=evidence.storage_ref,
                error=str(exc),
            )

    await db.delete(evidence)
    await db.flush()
    log.info("evidence_deleted", evidence_id=str(evidence_id), user_id=str(current_user.id))


# ---------------------------------------------------------------------------
# GET /evidence/{id}/download  — presigned URL
# ---------------------------------------------------------------------------


@router.get("/evidence/{evidence_id}/download", response_model=PresignedUrlResponse)
async def download_evidence(
    evidence_id: uuid.UUID,
    current_user: UserDep,
    db: DbDep,
) -> PresignedUrlResponse:
    stmt = select(EvidenceModel).where(EvidenceModel.id == evidence_id)
    evidence = (await db.execute(stmt)).scalar_one_or_none()
    _evidence_or_404(evidence)
    assert evidence is not None

    if not evidence.storage_ref:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No storage reference associated with this evidence record.",
        )

    try:
        from datetime import timedelta

        minio = MinioStorageClient()
        _ensure_evidence_bucket(minio)
        presigned_url = minio._client.presigned_get_object(
            bucket_name=EVIDENCE_BUCKET,
            object_name=evidence.storage_ref,
            expires=timedelta(seconds=PRESIGNED_EXPIRY_SECONDS),
        )
    except Exception as exc:
        log.error(
            "evidence_presign_failed",
            evidence_id=str(evidence_id),
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not generate presigned URL: {exc}",
        ) from exc

    return PresignedUrlResponse(url=presigned_url, expires_in_seconds=PRESIGNED_EXPIRY_SECONDS)
