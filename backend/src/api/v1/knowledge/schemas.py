"""Pydantic v2 schemas for the Knowledge Base ingestion API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, HttpUrl


class IngestRequest(BaseModel):
    """Request body for URL-based ingestion."""

    url: HttpUrl | None = None
    tags: list[str] = []


class IngestResponse(BaseModel):
    """Immediate response to an ingestion request (task is queued)."""

    job_id: str
    doc_id: str
    status: str = "queued"


class KnowledgeDocResponse(BaseModel):
    """Document metadata response."""

    doc_id: str
    source: str
    chunk_count: int
    tags: list[str]
    created_at: datetime
