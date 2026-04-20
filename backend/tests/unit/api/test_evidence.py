"""Tests for evidence tagging."""

import pytest
from unittest.mock import MagicMock


class TestEvidenceEndpoints:
    @pytest.mark.asyncio
    async def test_list_evidence(self):
        from src.api.v1.evidence import list_evidence

        result = await list_evidence(investigation_id="inv-1", current_user=MagicMock())
        assert result.tags == []
        assert result.total == 0

    @pytest.mark.asyncio
    async def test_create_evidence_tag(self):
        from src.api.v1.evidence import EvidenceTagCreate, create_evidence_tag

        body = EvidenceTagCreate(
            investigation_id="inv-1", tag_name="suspicious", notes="Needs review"
        )
        mock_user = MagicMock()
        mock_user.id = "user-1"
        result = await create_evidence_tag(
            investigation_id="inv-1", body=body, current_user=mock_user
        )
        assert result.tag_name == "suspicious"
        assert result.notes == "Needs review"
        assert result.created_by == "user-1"

    @pytest.mark.asyncio
    async def test_delete_evidence(self):
        from src.api.v1.evidence import delete_evidence_tag

        result = await delete_evidence_tag(
            investigation_id="inv-1", tag_id="tag-1", current_user=MagicMock()
        )
        assert result["status"] == "deleted"
        assert result["id"] == "tag-1"
