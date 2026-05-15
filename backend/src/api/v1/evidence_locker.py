"""Evidence Locker — chain of custody tracking with SHA-256 integrity.

Provides a tamper-evident evidence store with append-only custody log.
Each submission records the SHA-256 hash and timestamp so evidence
integrity can be verified at any point in the investigation lifecycle.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/evidence-locker", tags=["evidence-locker"])

# In-memory store (production: replace with DB table + MinIO for files)
_evidence_store: dict[str, dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CustodyEntry(BaseModel):
    action: str  # created, viewed, exported, modified, sealed
    timestamp: str
    user_id: str
    notes: str
    integrity_hash: str  # SHA-256 of (evidence_id + action + timestamp + user_id)


class EvidenceItem(BaseModel):
    id: str
    title: str
    type: str  # screenshot, document, url, note, artifact, log, pcap
    description: str
    investigation_id: str | None
    tags: list[str]
    chain_of_custody: list[CustodyEntry]
    hash_sha256: str | None
    content_hash_verified: bool
    size_bytes: int | None
    created_at: str
    created_by: str
    sealed: bool  # sealed items cannot be modified
    is_admissible: bool


class CreateEvidenceInput(BaseModel):
    title: str = Field(..., min_length=1)
    type: str = Field(..., pattern="^(screenshot|document|url|note|artifact|log|pcap|network_capture|memory_dump)$")
    description: str = Field(default="")
    investigation_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    hash_sha256: str | None = Field(None, description="SHA-256 of the original artifact for integrity verification")
    size_bytes: int | None = None
    content: str | None = Field(None, description="Raw content (for notes/URLs) — hashed server-side")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _custody_hash(evidence_id: str, action: str, timestamp: str, user_id: str) -> str:
    payload = f"{evidence_id}:{action}:{timestamp}:{user_id}"
    return hashlib.sha256(payload.encode()).hexdigest()


def _make_custody_entry(evidence_id: str, action: str, user_id: str, notes: str) -> CustodyEntry:
    ts = _now_iso()
    return CustodyEntry(
        action=action,
        timestamp=ts,
        user_id=user_id,
        notes=notes,
        integrity_hash=_custody_hash(evidence_id, action, ts, user_id),
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("", response_model=list[EvidenceItem])
async def list_evidence(
    current_user: Annotated[User, Depends(get_current_user)],
    investigation_id: str | None = None,
) -> list[EvidenceItem]:
    """List evidence items, optionally filtered by investigation."""
    items = [v for v in _evidence_store.values() if v.get("created_by") == str(current_user.id)]
    if investigation_id:
        items = [i for i in items if i.get("investigation_id") == investigation_id]
    return [EvidenceItem(**i) for i in items]


@router.post("", response_model=EvidenceItem, status_code=201)
async def create_evidence(
    data: CreateEvidenceInput,
    current_user: Annotated[User, Depends(get_current_user)],
) -> EvidenceItem:
    """Submit new evidence with automatic chain of custody logging."""
    eid = str(uuid.uuid4())
    now = _now_iso()
    user_id = str(current_user.id)

    # Server-side hash of content if provided and no explicit hash given
    computed_hash = data.hash_sha256
    if data.content and not computed_hash:
        computed_hash = hashlib.sha256(data.content.encode()).hexdigest()

    custody_entry = _make_custody_entry(eid, "created", user_id, "Initial evidence submission")

    item: dict[str, Any] = {
        "id": eid,
        "title": data.title,
        "type": data.type,
        "description": data.description,
        "investigation_id": data.investigation_id,
        "tags": data.tags,
        "chain_of_custody": [custody_entry.model_dump()],
        "hash_sha256": computed_hash,
        "content_hash_verified": computed_hash is not None,
        "size_bytes": data.size_bytes or (len(data.content.encode()) if data.content else None),
        "created_at": now,
        "created_by": user_id,
        "sealed": False,
        "is_admissible": True,
    }
    _evidence_store[eid] = item
    log.info("evidence_created", id=eid, type=data.type, user=user_id)
    return EvidenceItem(**item)


@router.get("/{evidence_id}", response_model=EvidenceItem)
async def get_evidence(
    evidence_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> EvidenceItem:
    """Retrieve evidence item and append a 'viewed' custody entry."""
    if evidence_id not in _evidence_store:
        raise HTTPException(status_code=404, detail="Evidence not found")
    item = _evidence_store[evidence_id]

    # Append view event to chain of custody
    entry = _make_custody_entry(evidence_id, "viewed", str(current_user.id), "Evidence viewed")
    item["chain_of_custody"].append(entry.model_dump())

    return EvidenceItem(**item)


@router.post("/{evidence_id}/seal", response_model=EvidenceItem)
async def seal_evidence(
    evidence_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> EvidenceItem:
    """Seal evidence — prevents further modification. Append seal entry."""
    if evidence_id not in _evidence_store:
        raise HTTPException(status_code=404, detail="Evidence not found")
    item = _evidence_store[evidence_id]
    if item["created_by"] != str(current_user.id):
        raise HTTPException(status_code=403, detail="Only the submitter can seal evidence")
    if item.get("sealed"):
        raise HTTPException(status_code=409, detail="Evidence is already sealed")

    entry = _make_custody_entry(evidence_id, "sealed", str(current_user.id), "Evidence sealed — integrity locked")
    item["chain_of_custody"].append(entry.model_dump())
    item["sealed"] = True

    log.info("evidence_sealed", id=evidence_id, user=str(current_user.id))
    return EvidenceItem(**item)


@router.post("/{evidence_id}/export", response_model=dict[str, Any])
async def export_evidence(
    evidence_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Export evidence with custody chain for legal/compliance use."""
    if evidence_id not in _evidence_store:
        raise HTTPException(status_code=404, detail="Evidence not found")
    item = _evidence_store[evidence_id]

    entry = _make_custody_entry(evidence_id, "exported", str(current_user.id), "Evidence exported for review")
    item["chain_of_custody"].append(entry.model_dump())

    return {
        "evidence": EvidenceItem(**item).model_dump(),
        "export_timestamp": _now_iso(),
        "exported_by": str(current_user.id),
        "custody_entries": len(item["chain_of_custody"]),
        "integrity_note": (
            f"SHA-256: {item['hash_sha256']}" if item.get("hash_sha256")
            else "No content hash — verify evidence integrity externally"
        ),
    }


@router.get("/{evidence_id}/verify", response_model=dict[str, Any])
async def verify_evidence(
    evidence_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Re-verify chain of custody integrity by recomputing each entry's hash. (#15)

    Compares the stored ``integrity_hash`` in each custody entry against a fresh
    computation of ``SHA-256(evidence_id:action:timestamp:user_id)``. Any mismatch
    indicates that the custody record was tampered with after it was written.
    """
    if evidence_id not in _evidence_store:
        raise HTTPException(status_code=404, detail="Evidence not found")
    item = _evidence_store[evidence_id]

    mismatches: list[dict[str, Any]] = []
    for i, entry in enumerate(item["chain_of_custody"]):
        expected = _custody_hash(
            evidence_id,
            entry["action"],
            entry["timestamp"],
            entry["user_id"],
        )
        if entry["integrity_hash"] != expected:
            mismatches.append({
                "entry_index": i,
                "action": entry["action"],
                "timestamp": entry["timestamp"],
                "stored_hash": entry["integrity_hash"],
                "expected_hash": expected,
            })

    is_intact = len(mismatches) == 0
    log.info(
        "evidence_verified",
        id=evidence_id,
        intact=is_intact,
        tampered_entries=len(mismatches),
    )
    return {
        "evidence_id": evidence_id,
        "is_intact": is_intact,
        "custody_entries_checked": len(item["chain_of_custody"]),
        "tampered_entries": mismatches,
        "verified_at": _now_iso(),
        "verified_by": str(current_user.id),
    }


@router.delete("/{evidence_id}", status_code=204)
async def delete_evidence(
    evidence_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Delete evidence. Sealed evidence cannot be deleted."""
    if evidence_id not in _evidence_store:
        raise HTTPException(status_code=404, detail="Evidence not found")
    item = _evidence_store[evidence_id]
    if item["created_by"] != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")
    if item.get("sealed"):
        raise HTTPException(status_code=409, detail="Sealed evidence cannot be deleted")
    del _evidence_store[evidence_id]
    log.info("evidence_deleted", id=evidence_id, user=str(current_user.id))
