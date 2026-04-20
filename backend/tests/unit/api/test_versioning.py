"""Tests for investigation versioning."""

import pytest
from unittest.mock import MagicMock


class TestVersioningEndpoints:
    @pytest.mark.asyncio
    async def test_list_versions(self):
        from src.api.v1.versioning import list_versions

        result = await list_versions(investigation_id="inv-1", current_user=MagicMock())
        assert result.versions == []
        assert result.total == 0

    @pytest.mark.asyncio
    async def test_create_version(self):
        from src.api.v1.versioning import VersionCreateRequest, create_version

        mock_user = MagicMock()
        mock_user.id = "user-1"
        body = VersionCreateRequest(change_summary="Added new scan results")
        result = await create_version(investigation_id="inv-1", body=body, current_user=mock_user)
        assert result.version_number == 1
        assert result.change_summary == "Added new scan results"
        assert result.created_by == "user-1"

    @pytest.mark.asyncio
    async def test_restore_version(self):
        from src.api.v1.versioning import restore_version

        result = await restore_version(
            investigation_id="inv-1", version_id="v-1", current_user=MagicMock()
        )
        assert result["status"] == "restored"
        assert result["version_id"] == "v-1"
