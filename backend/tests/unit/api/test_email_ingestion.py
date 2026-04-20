"""Tests for email ingestion."""
import pytest
from unittest.mock import MagicMock


class TestEmailIngestionEndpoints:
    @pytest.mark.asyncio
    async def test_ingest_email(self):
        from src.api.v1.email_ingestion import ingest_email, EmailIngestRequest

        body = EmailIngestRequest(
            body_text="Contact john@example.com or check 192.168.1.1 for details",
            from_address="sender@test.com",
        )
        result = await ingest_email(body=body, current_user=MagicMock())
        assert result.status == "processed"
        types = {e["type"] for e in result.extracted_entities}
        assert "email" in types
        assert "ip_address" in types

    @pytest.mark.asyncio
    async def test_get_config(self):
        from src.api.v1.email_ingestion import get_ingest_config

        result = await get_ingest_config(current_user=MagicMock())
        assert result.enabled is False
