"""User entity — represents an authenticated platform user."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
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
