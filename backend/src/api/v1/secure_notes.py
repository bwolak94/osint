from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import uuid, base64
from datetime import datetime

router = APIRouter(prefix="/api/v1/secure-notes", tags=["secure-notes"])

_notes: dict[str, dict] = {}


class SecureNote(BaseModel):
    id: str
    title: str
    content_encrypted: str  # In real impl, encrypted client-side
    tags: list[str]
    investigation_id: Optional[str]
    is_encrypted: bool
    created_at: str
    updated_at: str
    word_count: int


class CreateNoteInput(BaseModel):
    title: str
    content: str
    tags: list[str] = []
    investigation_id: Optional[str] = None


@router.get("", response_model=list[SecureNote])
async def list_notes(investigation_id: Optional[str] = None):
    notes = list(_notes.values())
    if investigation_id:
        notes = [n for n in notes if n.get("investigation_id") == investigation_id]
    return [SecureNote(**n) for n in notes]


@router.post("", response_model=SecureNote)
async def create_note(data: CreateNoteInput):
    nid = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    # Simulate base64 "encryption" for demo (real impl would use AES-GCM client-side)
    encrypted = base64.b64encode(data.content.encode()).decode()
    note = {
        "id": nid,
        "title": data.title,
        "content_encrypted": encrypted,
        "tags": data.tags,
        "investigation_id": data.investigation_id,
        "is_encrypted": True,
        "created_at": now,
        "updated_at": now,
        "word_count": len(data.content.split()),
    }
    _notes[nid] = note
    return SecureNote(**note)


@router.get("/{note_id}/decrypt")
async def decrypt_note(note_id: str):
    if note_id not in _notes:
        raise HTTPException(status_code=404, detail="Note not found")
    note = _notes[note_id]
    content = base64.b64decode(note["content_encrypted"]).decode()
    return {"content": content}


@router.delete("/{note_id}")
async def delete_note(note_id: str):
    if note_id not in _notes:
        raise HTTPException(status_code=404, detail="Note not found")
    del _notes[note_id]
    return {"deleted": True}
