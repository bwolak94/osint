"""Tests for redaction endpoints."""
import pytest
from unittest.mock import MagicMock


class TestRedactionEndpoints:
    async def test_apply_redaction_mask(self):
        from src.api.v1.redaction import apply_redaction, RedactRequest, get_encryptor

        body = RedactRequest(data={"email": "test@example.com", "title": "Test"}, mode="mask")
        result = await apply_redaction(body=body, current_user=MagicMock(), encryptor=get_encryptor())
        assert "*" in result.data["email"]
        assert result.data["title"] == "Test"

    async def test_apply_redaction_remove(self):
        from src.api.v1.redaction import apply_redaction, RedactRequest, get_encryptor

        body = RedactRequest(data={"email": "test@example.com", "title": "Test"}, mode="remove")
        result = await apply_redaction(body=body, current_user=MagicMock(), encryptor=get_encryptor())
        assert "email" not in result.data
        assert result.data["title"] == "Test"

    async def test_list_redaction_rules(self):
        from src.api.v1.redaction import list_redaction_rules

        result = await list_redaction_rules(current_user=MagicMock())
        assert "pii_fields" in result
