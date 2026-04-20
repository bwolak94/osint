"""Tests for UserSettings and SystemSettings entities."""

import pytest
from uuid import uuid4

from src.core.domain.entities.settings import UserSettings, SystemSettings


class TestUserSettingsEntity:
    def test_defaults(self):
        s = UserSettings(user_id=uuid4())
        assert s.theme == "dark"
        assert s.language == "pl"
        assert s.timezone == "Europe/Warsaw"
        assert s.default_scan_depth == 2
        assert s.data_retention_days == 90
        assert s.api_key_hash is None

    def test_update_returns_new_instance(self):
        s = UserSettings(user_id=uuid4())
        updated = s.update(theme="light", language="en")
        assert updated.theme == "light"
        assert updated.language == "en"
        assert s.theme == "dark"  # original unchanged

    def test_set_api_key(self):
        s = UserSettings(user_id=uuid4())
        with_key = s.set_api_key("hash123", "osint_abc")
        assert with_key.api_key_hash == "hash123"
        assert with_key.api_key_prefix == "osint_abc"
        assert with_key.api_key_created_at is not None

    def test_revoke_api_key(self):
        s = UserSettings(user_id=uuid4())
        with_key = s.set_api_key("hash", "pre")
        revoked = with_key.revoke_api_key()
        assert revoked.api_key_hash is None
        assert revoked.api_key_prefix is None
        assert revoked.api_key_created_at is None

    def test_update_preserves_other_fields(self):
        s = UserSettings(user_id=uuid4(), theme="light")
        updated = s.update(language="en")
        assert updated.theme == "light"
        assert updated.language == "en"


class TestSystemSettingsEntity:
    def test_defaults(self):
        s = SystemSettings()
        assert s.max_concurrent_browsers == 5
        assert s.maintenance_mode is False
        assert s.proxy_enabled is False

    def test_update(self):
        s = SystemSettings()
        updated = s.update(maintenance_mode=True, maintenance_message="Upgrading")
        assert updated.maintenance_mode is True
        assert updated.maintenance_message == "Upgrading"
        assert s.maintenance_mode is False  # original unchanged
