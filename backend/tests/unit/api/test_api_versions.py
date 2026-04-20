"""Tests for API versioning."""
import pytest


class TestAPIVersionEndpoints:
    async def test_list_versions(self):
        from src.api.v1.api_versions import list_api_versions
        result = await list_api_versions()
        assert result.current == "v1"
        assert len(result.versions) >= 1

    async def test_get_version_found(self):
        from src.api.v1.api_versions import get_version_info
        result = await get_version_info(version="v1")
        assert result.version == "v1"
        assert result.status == "stable"

    async def test_get_version_not_found(self):
        from src.api.v1.api_versions import get_version_info
        result = await get_version_info(version="v99")
        assert "error" in result
