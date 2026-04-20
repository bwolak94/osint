"""Use case: generate a new API key for a user."""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from src.core.domain.entities.settings import UserSettings
from src.core.domain.entities.types import SubscriptionTier
from src.core.ports.repositories import IUserRepository
from src.core.ports.settings_repository import IUserSettingsRepository


@dataclass
class ApiKeyResult:
    key: str  # Shown only once
    prefix: str
    created_at: datetime


class GenerateApiKeyUseCase:
    """Generate a cryptographically secure API key.

    Only available to PRO and ENTERPRISE users.
    The raw key is returned once; only its SHA-256 hash is stored.
    """

    def __init__(self, user_repo: IUserRepository, settings_repo: IUserSettingsRepository) -> None:
        self._user_repo = user_repo
        self._settings_repo = settings_repo

    async def execute(self, user_id: UUID) -> ApiKeyResult:
        user = await self._user_repo.get_by_id(user_id)
        if user is None:
            raise ValueError("User not found")

        if user.subscription_tier == SubscriptionTier.FREE:
            raise PermissionError("API key generation requires a PRO or ENTERPRISE subscription")

        raw_key = f"osint_{secrets.token_hex(32)}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        prefix = raw_key[:12]

        settings = await self._settings_repo.get_by_user_id(user_id)
        if settings is None:
            settings = UserSettings(user_id=user_id)

        updated = settings.set_api_key(key_hash, prefix)
        await self._settings_repo.save(updated)

        return ApiKeyResult(key=raw_key, prefix=prefix, created_at=updated.api_key_created_at)
