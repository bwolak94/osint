"""Tests for webhook trigger endpoints."""

import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException


class TestWebhookTriggerEndpoints:
    async def test_list_triggers_empty(self):
        from src.api.v1.webhook_triggers import list_webhook_triggers

        mock_user = MagicMock()
        result = await list_webhook_triggers(current_user=mock_user)
        assert result.triggers == []
        assert result.total == 0

    async def test_create_trigger(self):
        from src.api.v1.webhook_triggers import create_webhook_trigger, WebhookTriggerCreate

        mock_user = MagicMock()
        body = WebhookTriggerCreate(
            name="Email Scanner Trigger",
            input_type="email",
            scanners=["holehe", "breach"],
            auto_start=True,
        )
        with patch("src.config.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(base_url="http://localhost:8000")
            result = await create_webhook_trigger(body=body, current_user=mock_user)

        assert result.name == "Email Scanner Trigger"
        assert result.secret_token
        assert "invoke" in result.webhook_url
        assert result.is_active is True

    async def test_invoke_webhook_requires_secret(self):
        from src.api.v1.webhook_triggers import invoke_webhook, WebhookInvokePayload

        body = WebhookInvokePayload(input_value="test@example.com")
        with pytest.raises(HTTPException) as exc_info:
            await invoke_webhook(trigger_id="test", body=body, x_webhook_secret=None)
        assert exc_info.value.status_code == 401

    async def test_invoke_webhook_with_secret(self):
        from src.api.v1.webhook_triggers import invoke_webhook, WebhookInvokePayload

        body = WebhookInvokePayload(
            input_value="test@example.com",
            title="Test Investigation",
        )
        result = await invoke_webhook(trigger_id="test", body=body, x_webhook_secret="valid-secret")
        assert result["status"] == "accepted"
        assert "investigation_id" in result

    async def test_delete_trigger(self):
        from src.api.v1.webhook_triggers import delete_webhook_trigger

        mock_user = MagicMock()
        result = await delete_webhook_trigger(trigger_id="test-id", current_user=mock_user)
        assert result["status"] == "deleted"
