"""User entity — represents an authenticated platform user."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from uuid import UUID

from src.core.domain.entities.types import (
    Feature,
    SubscriptionTier,
    TIER_FEATURES,
    UserRole,
)
from src.core.domain.value_objects.email import Email


@dataclass
class User:
    """Mutable entity representing a platform user."""

    id: UUID
    email: Email
    hashed_password: str
    role: UserRole
    subscription_tier: SubscriptionTier
    is_active: bool
    created_at: datetime
    is_email_verified: bool = False
    failed_login_attempts: int = 0
    locked_until: datetime | None = None
    last_login_at: datetime | None = None

    # -- behaviour ----------------------------------------------------------

    def can_create_investigation(self) -> bool:
        """Only active analysts and admins may create investigations."""
        return self.is_active and self.role in {UserRole.ANALYST, UserRole.ADMIN}

    def can_use_feature(self, feature: Feature) -> bool:
        """Check whether the user's subscription tier grants access to *feature*."""
        allowed = TIER_FEATURES.get(self.subscription_tier, frozenset())
        return feature in allowed

    def upgrade_subscription(self, tier: SubscriptionTier) -> User:
        """Return a new User instance with the subscription tier changed."""
        return replace(self, subscription_tier=tier)

    def is_locked(self) -> bool:
        """Return True if the account is currently locked."""
        if self.locked_until is None:
            return False
        return self.locked_until > datetime.now(timezone.utc)

    def record_failed_login(self) -> User:
        """Increment failed login counter and lock the account after repeated failures.

        Lockout schedule:
        - 5 failed attempts  -> 15 minutes
        - 10 failed attempts -> 1 hour
        - 15+ failed attempts -> 24 hours
        """
        new_count = self.failed_login_attempts + 1
        now = datetime.now(timezone.utc)
        locked_until: datetime | None = None

        if new_count >= 15:
            locked_until = now + timedelta(hours=24)
        elif new_count >= 10:
            locked_until = now + timedelta(hours=1)
        elif new_count >= 5:
            locked_until = now + timedelta(minutes=15)

        return replace(
            self,
            failed_login_attempts=new_count,
            locked_until=locked_until,
        )

    def record_successful_login(self) -> User:
        """Reset the failed login counter and record the login timestamp."""
        return replace(
            self,
            failed_login_attempts=0,
            locked_until=None,
            last_login_at=datetime.now(timezone.utc),
        )

    def change_password(self, new_hashed_password: str) -> User:
        """Return a new User instance with an updated password hash."""
        return replace(self, hashed_password=new_hashed_password)

    def verify_email(self) -> User:
        """Return a new User instance with the email marked as verified."""
        return replace(self, is_email_verified=True)
