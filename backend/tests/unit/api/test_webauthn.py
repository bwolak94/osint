"""Tests for WebAuthn endpoints."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock


class TestWebAuthnEndpoints:
    """Tests for the WebAuthn registration flow."""

    async def test_register_begin_returns_challenge(self):
        """Begin registration should return a challenge and RP info."""
        from src.api.v1.auth.webauthn import webauthn_register_begin

        mock_user = {"sub": "test-user-id", "email": "test@example.com"}
        result = await webauthn_register_begin(current_user=mock_user)

        assert result.challenge
        assert result.rp["name"] == "OSINT Platform"
        assert len(result.pub_key_cred_params) == 2
        assert result.timeout == 60000

    async def test_register_complete_stores_credential(self):
        """Complete registration should accept and confirm credential."""
        from src.api.v1.auth.webauthn import webauthn_register_complete, WebAuthnRegisterCompleteRequest

        mock_user = {"sub": "test-user-id", "email": "test@example.com"}
        body = WebAuthnRegisterCompleteRequest(
            credential_id="dGVzdC1jcmVk",
            client_data_json="dGVzdC1jbGllbnQ=",
            attestation_object="dGVzdC1hdHRlc3Q=",
            device_name="Test Device",
        )
        result = await webauthn_register_complete(body=body, current_user=mock_user)

        assert result["status"] == "registered"
        assert result["device_name"] == "Test Device"

    async def test_list_credentials_returns_empty(self):
        """List credentials should return empty list initially."""
        from src.api.v1.auth.webauthn import list_webauthn_credentials

        mock_user = {"sub": "test-user-id"}
        result = await list_webauthn_credentials(current_user=mock_user)
        assert result == []

    async def test_delete_credential(self):
        """Delete credential should return deleted status."""
        from src.api.v1.auth.webauthn import delete_webauthn_credential

        mock_user = {"sub": "test-user-id"}
        result = await delete_webauthn_credential(credential_id="test-cred", current_user=mock_user)
        assert result["status"] == "deleted"
