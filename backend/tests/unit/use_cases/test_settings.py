"""Tests for settings use cases."""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from src.core.domain.entities.settings import UserSettings, SystemSettings
from src.core.domain.entities.user import User
from src.core.domain.entities.types import UserRole, SubscriptionTier
from src.core.domain.value_objects.email import Email
from src.core.use_cases.settings.generate_api_key import GenerateApiKeyUseCase


class FakeUserRepo:
    def __init__(self):
        self._users = {}

    async def get_by_id(self, user_id):
        return self._users.get(user_id)

    async def get_by_email(self, email):
        return None

    async def save(self, user):
        self._users[user.id] = user
        return user

    async def delete(self, user_id):
        self._users.pop(user_id, None)

    def add(self, user):
        self._users[user.id] = user


class FakeSettingsRepo:
    def __init__(self):
        self._settings = {}

    async def get_by_user_id(self, user_id):
        return self._settings.get(user_id)

    async def save(self, settings):
        self._settings[settings.user_id] = settings
        return settings

    async def delete(self, user_id):
        self._settings.pop(user_id, None)


def make_user(tier=SubscriptionTier.PRO, **kwargs):
    uid = kwargs.pop("user_id", uuid4())
    return User(
        id=uid,
        email=Email("user@example.com"),
        hashed_password="hashed",
        role=UserRole.ANALYST,
        subscription_tier=tier,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )


class TestUserSettings:
    def test_default_settings(self):
        s = UserSettings(user_id=uuid4())
        assert s.theme == "dark"
        assert s.language == "pl"
        assert s.default_scan_depth == 2

    def test_update_theme(self):
        s = UserSettings(user_id=uuid4())
        updated = s.update(theme="light")
        assert updated.theme == "light"
        # Original is a mutable dataclass so update() returns a new copy
        assert updated is not s

    def test_set_api_key(self):
        s = UserSettings(user_id=uuid4())
        updated = s.set_api_key("hash123", "osint_abc")
        assert updated.api_key_hash == "hash123"
        assert updated.api_key_prefix == "osint_abc"
        assert updated.api_key_created_at is not None

    def test_revoke_api_key(self):
        s = UserSettings(user_id=uuid4())
        with_key = s.set_api_key("hash", "prefix")
        revoked = with_key.revoke_api_key()
        assert revoked.api_key_hash is None
        assert revoked.api_key_prefix is None

    def test_update_multiple_fields(self):
        s = UserSettings(user_id=uuid4())
        updated = s.update(theme="light", language="en", default_scan_depth=3)
        assert updated.theme == "light"
        assert updated.language == "en"
        assert updated.default_scan_depth == 3


class TestSystemSettings:
    def test_defaults(self):
        s = SystemSettings()
        assert s.max_concurrent_browsers == 5
        assert s.maintenance_mode is False

    def test_update(self):
        s = SystemSettings()
        updated = s.update(maintenance_mode=True, maintenance_message="Updating")
        assert updated.maintenance_mode is True
        assert updated.maintenance_message == "Updating"


class TestGenerateApiKey:
    @pytest.fixture
    def deps(self):
        return {
            "user_repo": FakeUserRepo(),
            "settings_repo": FakeSettingsRepo(),
        }

    async def test_pro_user_gets_api_key(self, deps):
        user = make_user(tier=SubscriptionTier.PRO)
        deps["user_repo"].add(user)

        uc = GenerateApiKeyUseCase(**deps)
        result = await uc.execute(user.id)

        assert result.key.startswith("osint_")
        assert len(result.key) > 20
        assert result.prefix == result.key[:12]

    async def test_free_user_cannot_get_key(self, deps):
        user = make_user(tier=SubscriptionTier.FREE)
        deps["user_repo"].add(user)

        uc = GenerateApiKeyUseCase(**deps)
        with pytest.raises(PermissionError):
            await uc.execute(user.id)

    async def test_enterprise_user_gets_key(self, deps):
        user = make_user(tier=SubscriptionTier.ENTERPRISE)
        deps["user_repo"].add(user)

        uc = GenerateApiKeyUseCase(**deps)
        result = await uc.execute(user.id)
        assert result.key.startswith("osint_")

    async def test_key_hash_stored_not_plaintext(self, deps):
        user = make_user(tier=SubscriptionTier.PRO)
        deps["user_repo"].add(user)

        uc = GenerateApiKeyUseCase(**deps)
        result = await uc.execute(user.id)

        settings = await deps["settings_repo"].get_by_user_id(user.id)
        assert settings.api_key_hash is not None
        assert settings.api_key_hash != result.key  # hash != plaintext

    async def test_nonexistent_user_raises(self, deps):
        uc = GenerateApiKeyUseCase(**deps)
        with pytest.raises(ValueError):
            await uc.execute(uuid4())
