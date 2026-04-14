"""User settings endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends

from src.api.v1.settings.schemas import UserSettingsResponse, UserSettingsUpdate
from src.dependencies import get_current_user

router = APIRouter()


@router.get("/", response_model=UserSettingsResponse)
async def get_settings(
    user: Annotated[dict, Depends(get_current_user)],
) -> UserSettingsResponse:
    """Retrieve the current user's settings.

    Stub: returns default settings.
    """
    return UserSettingsResponse(
        user_id=user["user_id"],
        notifications_enabled=True,
        theme="dark",
        language="en",
    )


@router.put("/", response_model=UserSettingsResponse)
async def update_settings(
    body: UserSettingsUpdate,
    user: Annotated[dict, Depends(get_current_user)],
) -> UserSettingsResponse:
    """Update the current user's settings.

    Stub: echoes back the submitted values.
    """
    return UserSettingsResponse(
        user_id=user["user_id"],
        notifications_enabled=body.notifications_enabled if body.notifications_enabled is not None else True,
        theme=body.theme or "dark",
        language=body.language or "en",
    )
