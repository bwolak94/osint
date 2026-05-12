from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import uuid
from datetime import datetime

router = APIRouter(prefix="/api/v1/collaboration", tags=["collaboration"])

_sessions: dict[str, dict] = {}
_activity: list[dict] = []

class CollabSession(BaseModel):
    id: str
    investigation_id: str
    name: str
    created_by: str
    participants: list[dict]
    status: str
    created_at: str
    share_link: str

class CollabActivity(BaseModel):
    id: str
    session_id: str
    user: str
    action: str
    target: str
    timestamp: str

@router.get("/sessions", response_model=list[CollabSession])
async def list_sessions():
    return [CollabSession(**s) for s in _sessions.values()]

@router.post("/sessions", response_model=CollabSession)
async def create_session(investigation_id: str, name: str):
    sid = str(uuid.uuid4())
    share_token = uuid.uuid4().hex[:16]
    session = {
        "id": sid, "investigation_id": investigation_id, "name": name,
        "created_by": "current_user",
        "participants": [{"user": "current_user", "role": "owner", "online": True}],
        "status": "active", "created_at": datetime.utcnow().isoformat(),
        "share_link": f"/collab/join/{share_token}"
    }
    _sessions[sid] = session
    return CollabSession(**session)

@router.get("/sessions/{session_id}/activity", response_model=list[CollabActivity])
async def get_activity(session_id: str):
    return [CollabActivity(**a) for a in _activity if a.get("session_id") == session_id]

@router.get("/online-users")
async def get_online_users():
    users = [
        {"user": "alice@team.com", "avatar": "A", "current_page": "/investigations/123", "online": True},
        {"user": "bob@team.com", "avatar": "B", "current_page": "/scanners", "online": True},
    ]
    return {"users": users, "total_online": len(users)}
