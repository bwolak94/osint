from __future__ import annotations
from pydantic import BaseModel, EmailStr


class EmailPivotRequest(BaseModel):
    email: str
    hibp_key: str = ""


class LinkedAccountSchema(BaseModel):
    platform: str
    profile_url: str | None = None
    display_name: str | None = None
    avatar_url: str | None = None
    exists: bool = True


class EmailPivotResponse(BaseModel):
    email: str
    domain: str | None = None
    gravatar_exists: bool = False
    gravatar_display_name: str | None = None
    gravatar_avatar_url: str | None = None
    gravatar_profile_url: str | None = None
    github_username: str | None = None
    github_profile_url: str | None = None
    hibp_breaches: list[str] = []
    hibp_checked: bool = False
    disposable: bool = False
    linked_accounts: list[LinkedAccountSchema] = []
