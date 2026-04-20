"""Pydantic schemas for the document metadata API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocMetadataResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    file_hash: str
    file_size: int
    mime_type: str
    doc_format: str | None
    author: str | None
    creator_tool: str | None
    company: str | None
    last_modified_by: str | None
    created_at_doc: datetime | None
    modified_at_doc: datetime | None
    revision_count: int | None
    has_macros: bool
    has_hidden_content: bool
    has_tracked_changes: bool
    gps_lat: float | None
    gps_lon: float | None
    raw_metadata: dict
    embedded_files: list[str]
    created_at: datetime


class DocMetadataListResponse(BaseModel):
    items: list[DocMetadataResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
