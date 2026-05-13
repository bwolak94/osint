from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel


class HttpFingerprintRequest(BaseModel):
    url: str


class SecurityScoreSchema(BaseModel):
    present: list[str] = []
    missing: list[str] = []
    score: int = 0


class HttpFingerprintResponse(BaseModel):
    id: uuid.UUID | None = None
    created_at: datetime | None = None
    url: str
    final_url: str | None = None
    status_code: int | None = None
    technologies: list[str] = []
    headers: dict[str, str] = {}
    security: SecurityScoreSchema = SecurityScoreSchema()
    cdn: str | None = None
    ip: str | None = None
    error: str | None = None


class HttpFingerprintListResponse(BaseModel):
    items: list[HttpFingerprintResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
