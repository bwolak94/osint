"""Tests for bulk actions."""
import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest

# Prevent the deep dependency chain from auth.dependencies by pre-seeding
# a fake module with a mock get_current_user before bulk_actions is imported.
_STUB_MODULES = (
    "passlib",
    "passlib.context",
    "jose",
    "redis",
    "redis.asyncio",
    "asyncpg",
)

for _mod_name in _STUB_MODULES:
    if _mod_name not in sys.modules:
        _m = ModuleType(_mod_name)
        _m.__dict__.setdefault("CryptContext", MagicMock())
        _m.__dict__.setdefault("jwt", MagicMock())
        _m.__dict__.setdefault("JWTError", Exception)
        _m.__dict__.setdefault("Redis", MagicMock())
        sys.modules[_mod_name] = _m


class TestBulkActionEndpoints:
    @pytest.mark.asyncio
    async def test_bulk_action_archive(self):
        from src.api.v1.bulk_actions import BulkActionRequest, bulk_action

        body = BulkActionRequest(investigation_ids=["inv-1", "inv-2"], action="archive")
        result = await bulk_action(body=body, current_user=MagicMock())

        assert result.action == "archive"
        assert result.total == 2
        assert result.succeeded == 2
        assert result.failed == 0

    @pytest.mark.asyncio
    async def test_bulk_import(self):
        from src.api.v1.bulk_actions import BulkImportRequest, bulk_import

        body = BulkImportRequest(investigations=[{"title": "Test 1"}, {"title": "Test 2"}])
        result = await bulk_import(body=body, current_user=MagicMock())

        assert result.total == 2
        assert result.created == 2

    @pytest.mark.asyncio
    async def test_bulk_export(self):
        from src.api.v1.bulk_actions import bulk_export

        result = await bulk_export(
            body={"investigation_ids": ["inv-1"], "format": "json"},
            current_user=MagicMock(),
        )

        assert result["status"] == "processing"
