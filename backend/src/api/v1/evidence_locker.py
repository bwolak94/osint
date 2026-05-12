from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import uuid
from datetime import datetime

router = APIRouter(prefix="/api/v1/evidence-locker", tags=["evidence-locker"])

# In-memory store for demo
_evidence_store: dict[str, dict] = {}

class EvidenceItem(BaseModel):
    id: str
    title: str
    type: str  # screenshot, document, url, note, artifact, log
    description: str
    investigation_id: Optional[str]
    tags: list[str]
    chain_of_custody: list[dict]
    hash_sha256: Optional[str]
    size_bytes: Optional[int]
    created_at: str
    created_by: str
    is_admissible: bool

class CreateEvidenceInput(BaseModel):
    title: str
    type: str
    description: str
    investigation_id: Optional[str] = None
    tags: list[str] = []
    hash_sha256: Optional[str] = None

@router.get("", response_model=list[EvidenceItem])
async def list_evidence(investigation_id: Optional[str] = None):
    items = list(_evidence_store.values())
    if investigation_id:
        items = [i for i in items if i.get("investigation_id") == investigation_id]
    return [EvidenceItem(**i) for i in items]

@router.post("", response_model=EvidenceItem)
async def create_evidence(data: CreateEvidenceInput):
    eid = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    item = {
        "id": eid,
        "title": data.title,
        "type": data.type,
        "description": data.description,
        "investigation_id": data.investigation_id,
        "tags": data.tags,
        "chain_of_custody": [{"action": "created", "timestamp": now, "user": "current_user", "notes": "Initial evidence submission"}],
        "hash_sha256": data.hash_sha256,
        "size_bytes": None,
        "created_at": now,
        "created_by": "current_user",
        "is_admissible": True,
    }
    _evidence_store[eid] = item
    return EvidenceItem(**item)

@router.get("/{evidence_id}", response_model=EvidenceItem)
async def get_evidence(evidence_id: str):
    if evidence_id not in _evidence_store:
        raise HTTPException(status_code=404, detail="Evidence not found")
    return EvidenceItem(**_evidence_store[evidence_id])

@router.delete("/{evidence_id}")
async def delete_evidence(evidence_id: str):
    if evidence_id not in _evidence_store:
        raise HTTPException(status_code=404, detail="Evidence not found")
    del _evidence_store[evidence_id]
    return {"deleted": True}
