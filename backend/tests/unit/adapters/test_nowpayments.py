"""Tests for NowPayments webhook signature verification."""

import hashlib
import hmac
import json
import pytest

from src.adapters.payments.crypto_gateway import NowPaymentsGateway


class TestWebhookVerification:
    @pytest.fixture
    def gateway(self):
        return NowPaymentsGateway(api_key="test-key", ipn_secret="test-secret", sandbox=True)

    def _sign(self, payload: dict, secret: str) -> str:
        sorted_json = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hmac.new(secret.encode(), sorted_json, hashlib.sha512).hexdigest()

    async def test_valid_signature_returns_true(self, gateway):
        payload = {"payment_id": "123", "payment_status": "finished", "order_id": "abc"}
        sig = self._sign(payload, "test-secret")
        result = await gateway.verify_webhook_signature(json.dumps(payload).encode(), sig)
        assert result is True

    async def test_invalid_signature_returns_false(self, gateway):
        payload = {"payment_id": "123", "payment_status": "finished"}
        result = await gateway.verify_webhook_signature(json.dumps(payload).encode(), "invalid_sig")
        assert result is False

    async def test_tampered_payload_fails(self, gateway):
        original = {"payment_id": "123", "payment_status": "finished"}
        sig = self._sign(original, "test-secret")
        tampered = {"payment_id": "123", "payment_status": "failed"}
        result = await gateway.verify_webhook_signature(json.dumps(tampered).encode(), sig)
        assert result is False

    async def test_empty_signature_returns_false(self, gateway):
        result = await gateway.verify_webhook_signature(b'{"test": 1}', "")
        assert result is False

    async def test_empty_secret_returns_false(self):
        gateway = NowPaymentsGateway(api_key="key", ipn_secret="", sandbox=True)
        result = await gateway.verify_webhook_signature(b'{"test": 1}', "some_sig")
        assert result is False

    async def test_invalid_json_returns_false(self, gateway):
        result = await gateway.verify_webhook_signature(b'not json', "some_sig")
        assert result is False
