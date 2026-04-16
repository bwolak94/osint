"""Pydantic schemas for settings endpoints."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class UserSettingsResponse(BaseModel):
    user_id: UUID
    theme: str
    language: str
    date_format: str
    timezone: str
    email_on_scan_complete: bool
    email_on_new_findings: bool
    email_weekly_digest: bool
    default_scan_depth: int
    default_enabled_scanners: list[str]
    default_tags: list[str]
    anonymize_exports: bool
    data_retention_days: int
    has_api_key: bool = False
    api_key_prefix: str | None = None
    api_key_created_at: datetime | None = None
    gdpr_consent_given_at: datetime | None = None
    marketing_consent: bool = False
    updated_at: datetime


class UserSettingsUpdate(BaseModel):
    theme: Literal["dark", "light", "system"] | None = None
    language: Literal["pl", "en"] | None = None
    date_format: str | None = None
    timezone: str | None = None
    email_on_scan_complete: bool | None = None
    email_on_new_findings: bool | None = None
    email_weekly_digest: bool | None = None
    default_scan_depth: int | None = Field(None, ge=1, le=5)
    default_enabled_scanners: list[str] | None = None
    default_tags: list[str] | None = None
    anonymize_exports: bool | None = None
    data_retention_days: int | None = Field(None, ge=1, le=365)
    marketing_consent: bool | None = None


class SystemSettingsResponse(BaseModel):
    max_concurrent_browsers: int
    max_scan_depth_global: int
    default_request_delay_ms: int
    free_tier_investigations_per_month: int
    free_tier_scans_per_day: int
    proxy_enabled: bool
    proxy_rotation_enabled: bool
    maintenance_mode: bool
    maintenance_message: str
    updated_at: datetime


class SystemSettingsUpdate(BaseModel):
    max_concurrent_browsers: int | None = Field(None, ge=1, le=20)
    max_scan_depth_global: int | None = Field(None, ge=1, le=10)
    default_request_delay_ms: int | None = Field(None, ge=500, le=10000)
    free_tier_investigations_per_month: int | None = Field(None, ge=0, le=100)
    free_tier_scans_per_day: int | None = Field(None, ge=0, le=100)
    proxy_enabled: bool | None = None
    proxy_rotation_enabled: bool | None = None
    maintenance_mode: bool | None = None
    maintenance_message: str | None = None


class ApiKeyResponse(BaseModel):
    key: str  # Only shown once
    prefix: str
    created_at: datetime
    warning: str = "Save this key now. It will not be shown again."


class ApiKeyInfoResponse(BaseModel):
    has_key: bool
    prefix: str | None = None
    created_at: datetime | None = None


class GdprExportResponse(BaseModel):
    message: str
    job_id: str | None = None


class GdprDeleteResponse(BaseModel):
    message: str
    scheduled_for: datetime | None = None


class SessionResponse(BaseModel):
    id: str
    ip_address: str | None
    user_agent: str | None
    created_at: datetime
    is_current: bool = False


class MessageResponse(BaseModel):
    message: str
