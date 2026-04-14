"""User settings Pydantic schemas."""

from pydantic import BaseModel


class UserSettingsUpdate(BaseModel):
    """Request body for updating user settings."""

    notifications_enabled: bool | None = None
    theme: str | None = None
    language: str | None = None


class UserSettingsResponse(BaseModel):
    """Response schema for user settings."""

    user_id: str
    notifications_enabled: bool
    theme: str
    language: str
