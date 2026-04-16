"""Settings entities for user and system configuration."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID


@dataclass
class UserSettings:
    """Per-user configuration and preferences."""

    user_id: UUID

    # UI preferences
    theme: Literal["dark", "light", "system"] = "dark"
    language: Literal["pl", "en"] = "pl"
    date_format: str = "DD.MM.YYYY"
    timezone: str = "Europe/Warsaw"

    # Notification preferences
    email_on_scan_complete: bool = True
    email_on_new_findings: bool = False
    email_weekly_digest: bool = True

    # Investigation defaults
    default_scan_depth: int = 2
    default_enabled_scanners: list[str] = field(default_factory=lambda: ["holehe", "maigret"])
    default_tags: list[str] = field(default_factory=list)

    # Privacy
    anonymize_exports: bool = False
    data_retention_days: int = 90

    # API access (PRO+)
    api_key_hash: str | None = None
    api_key_prefix: str | None = None  # First 8 chars for identification
    api_key_created_at: datetime | None = None

    # GDPR
    gdpr_consent_given_at: datetime | None = None
    marketing_consent: bool = False

    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def update(self, **kwargs) -> UserSettings:
        """Return a new instance with updated fields."""
        return replace(self, updated_at=datetime.now(timezone.utc), **kwargs)

    def set_api_key(self, key_hash: str, prefix: str) -> UserSettings:
        """Store a new API key hash."""
        return replace(
            self,
            api_key_hash=key_hash,
            api_key_prefix=prefix,
            api_key_created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    def revoke_api_key(self) -> UserSettings:
        """Remove the API key."""
        return replace(
            self,
            api_key_hash=None,
            api_key_prefix=None,
            api_key_created_at=None,
            updated_at=datetime.now(timezone.utc),
        )


@dataclass
class SystemSettings:
    """Global system configuration — admin only."""

    # Scanners
    max_concurrent_browsers: int = 5
    max_scan_depth_global: int = 5
    default_request_delay_ms: int = 2000

    # Rate limiting per tier
    free_tier_investigations_per_month: int = 3
    free_tier_scans_per_day: int = 5

    # Proxy
    proxy_enabled: bool = False
    proxy_rotation_enabled: bool = False

    # Maintenance
    maintenance_mode: bool = False
    maintenance_message: str = ""

    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def update(self, **kwargs) -> SystemSettings:
        return replace(self, updated_at=datetime.now(timezone.utc), **kwargs)
