"""Real-time presence and cursor tracking endpoints."""

from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.api.v1.auth.dependencies import get_current_user

log = structlog.get_logger()
router = APIRouter()

# In-memory presence store (production would use Redis)
_presence_store: dict[str, dict[str, Any]] = {}

CURSOR_COLORS = ["#6366f1", "#ec4899", "#f59e0b", "#10b981", "#3b82f6", "#8b5cf6", "#ef4444", "#14b8a6"]


class PresenceUpdate(BaseModel):
    investigation_id: str
    cursor_position: dict[str, float] | None = None
    selected_node_id: str | None = None


class UserPresence(BaseModel):
    user_id: str
    email: str
    investigation_id: str
    cursor_position: dict[str, float] | None
    selected_node_id: str | None
    color: str
    last_seen_at: str


class PresenceListResponse(BaseModel):
    users: list[UserPresence]
    total: int


@router.post("/presence/heartbeat")
async def presence_heartbeat(
    body: PresenceUpdate,
    current_user: Any = Depends(get_current_user),
) -> dict[str, str]:
    """Update presence/cursor position for the current user."""
    user_id = str(getattr(current_user, "id", "unknown"))
    email = str(getattr(current_user, "email", "unknown"))

    key = f"{body.investigation_id}:{user_id}"
    color_idx = hash(user_id) % len(CURSOR_COLORS)

    _presence_store[key] = {
        "user_id": user_id,
        "email": email,
        "investigation_id": body.investigation_id,
        "cursor_position": body.cursor_position,
        "selected_node_id": body.selected_node_id,
        "color": CURSOR_COLORS[color_idx],
        "last_seen_at": datetime.now(timezone.utc).isoformat(),
    }

    return {"status": "ok"}


@router.get("/presence/{investigation_id}", response_model=PresenceListResponse)
async def get_presence(
    investigation_id: str,
    current_user: Any = Depends(get_current_user),
) -> PresenceListResponse:
    """Get all active users in an investigation."""
    now = datetime.now(timezone.utc)
    users = []
    for key, data in list(_presence_store.items()):
        if not key.startswith(f"{investigation_id}:"):
            continue
        # Expire after 60 seconds of inactivity
        last_seen = datetime.fromisoformat(data["last_seen_at"])
        if (now - last_seen).total_seconds() > 60:
            del _presence_store[key]
            continue
        users.append(UserPresence(**data))

    return PresenceListResponse(users=users, total=len(users))


@router.delete("/presence/{investigation_id}")
async def leave_presence(
    investigation_id: str,
    current_user: Any = Depends(get_current_user),
) -> dict[str, str]:
    """Remove current user from presence in an investigation."""
    user_id = str(getattr(current_user, "id", "unknown"))
    key = f"{investigation_id}:{user_id}"
    _presence_store.pop(key, None)
    return {"status": "left"}
