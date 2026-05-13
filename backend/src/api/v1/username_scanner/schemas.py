from __future__ import annotations
from pydantic import BaseModel


class UsernameScanRequest(BaseModel):
    username: str


class PlatformResultSchema(BaseModel):
    platform: str
    url: str
    found: bool
    status_code: int | None = None
    error: str | None = None


class UsernameScanResponse(BaseModel):
    username: str
    total_checked: int
    found: list[PlatformResultSchema] = []
    not_found: list[PlatformResultSchema] = []
    errors: list[PlatformResultSchema] = []
