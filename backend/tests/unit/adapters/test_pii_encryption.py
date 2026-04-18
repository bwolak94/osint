"""Tests for PII encryption."""
import pytest

from src.adapters.security.pii_encryption import PIIEncryptor


class TestPIIEncryptor:
    def test_mask_email(self):
        enc = PIIEncryptor()
        result = enc.mask_field("john@example.com", "email")
        assert result.startswith("j")
        assert "@example.com" in result
        assert "*" in result

    def test_mask_phone(self):
        enc = PIIEncryptor()
        result = enc.mask_field("+48123456789", "phone")
        assert result.startswith("+48")
        assert result.endswith("89")
        assert "*" in result

    def test_hash_field(self):
        enc = PIIEncryptor()
        result = enc.hash_field("test@example.com")
        assert len(result) == 64  # SHA-256

    def test_redact_pii_in_dict(self):
        enc = PIIEncryptor()
        data = {"email": "john@example.com", "title": "Investigation", "phone": "+48123456789"}
        result = enc.redact_pii_in_dict(data)
        assert result["title"] == "Investigation"
        assert "*" in result["email"]
        assert "*" in result["phone"]

    def test_encrypt_without_key(self):
        enc = PIIEncryptor(key="")
        result = enc.encrypt_field("test")
        assert result == "test"  # No key = passthrough

    def test_redact_nested(self):
        enc = PIIEncryptor()
        data = {"info": {"email": "john@example.com", "name": "John Doe"}, "id": "123"}
        result = enc.redact_pii_in_dict(data)
        assert "*" in result["info"]["email"]
        assert result["id"] == "123"
