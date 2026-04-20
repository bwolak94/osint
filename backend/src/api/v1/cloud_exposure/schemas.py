"""Pydantic schemas for cloud storage exposure API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BucketSchema(BaseModel):
    name: str
    provider: str
    url: str
    is_public: bool
    file_count: int
    sample_files: list[str]
    has_sensitive_files: bool
    sensitive_file_count: int


class CloudExposureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    target: str
    total_buckets: int
    public_buckets: int
    sensitive_findings: int
    buckets: list[BucketSchema]
    created_at: datetime


class CloudExposureListResponse(BaseModel):
    items: list[CloudExposureResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class CloudExposureRequest(BaseModel):
    target: str
