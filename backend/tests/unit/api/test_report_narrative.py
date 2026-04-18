"""Tests for report narrative."""
import pytest
from unittest.mock import MagicMock


class TestReportNarrativeEndpoints:
    @pytest.mark.asyncio
    async def test_generate_narrative(self):
        from src.api.v1.report_narrative import generate_narrative, NarrativeRequest

        body = NarrativeRequest(
            investigation_id="inv-1",
            scan_results=[{"scanner_name": "shodan", "extracted_identifiers": ["port:80"]}],
        )
        result = await generate_narrative(body=body, current_user=MagicMock())
        assert result.investigation_id == "inv-1"
        assert "executive_summary" in result.sections
        assert result.word_count > 0

    @pytest.mark.asyncio
    async def test_list_tones(self):
        from src.api.v1.report_narrative import list_tones

        result = await list_tones(current_user=MagicMock())
        assert len(result["tones"]) == 4
