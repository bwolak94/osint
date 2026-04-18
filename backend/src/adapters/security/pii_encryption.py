"""Field-level PII encryption for sensitive OSINT data."""
import base64
import hashlib
import os
from typing import Any

import structlog

log = structlog.get_logger()


class PIIEncryptor:
    """Encrypt/decrypt PII fields using Fernet-compatible symmetric encryption."""

    PII_FIELDS = {"email", "phone", "name", "address", "ssn", "nip", "ip_address", "password_hash"}

    def __init__(self, key: str | None = None) -> None:
        self._key = key or os.environ.get("PII_ENCRYPTION_KEY", "")

    def encrypt_field(self, value: str) -> str:
        if not self._key or not value:
            return value
        try:
            from cryptography.fernet import Fernet

            f = Fernet(self._key.encode() if isinstance(self._key, str) else self._key)
            return f.encrypt(value.encode()).decode()
        except ImportError:
            log.warning("cryptography package not installed, PII encryption disabled")
            return value
        except Exception as e:
            log.error("PII encryption failed", error=str(e))
            return value

    def decrypt_field(self, value: str) -> str:
        if not self._key or not value:
            return value
        try:
            from cryptography.fernet import Fernet

            f = Fernet(self._key.encode() if isinstance(self._key, str) else self._key)
            return f.decrypt(value.encode()).decode()
        except ImportError:
            return value
        except Exception as e:
            log.error("PII decryption failed", error=str(e))
            return value

    def mask_field(self, value: str, field_type: str = "default") -> str:
        if not value:
            return value
        if field_type == "email":
            parts = value.split("@")
            if len(parts) == 2:
                local = parts[0]
                return f"{local[0]}{'*' * (len(local) - 1)}@{parts[1]}"
        if field_type == "phone":
            return value[:3] + "*" * (len(value) - 5) + value[-2:]
        if len(value) > 4:
            return value[:2] + "*" * (len(value) - 4) + value[-2:]
        return "*" * len(value)

    def hash_field(self, value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()

    def encrypt_pii_in_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        result = {}
        for key, val in data.items():
            if isinstance(val, str) and key.lower() in self.PII_FIELDS:
                result[key] = self.encrypt_field(val)
            elif isinstance(val, dict):
                result[key] = self.encrypt_pii_in_dict(val)
            else:
                result[key] = val
        return result

    def redact_pii_in_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        result = {}
        for key, val in data.items():
            if isinstance(val, str) and key.lower() in self.PII_FIELDS:
                result[key] = self.mask_field(val, key.lower())
            elif isinstance(val, dict):
                result[key] = self.redact_pii_in_dict(val)
            else:
                result[key] = val
        return result
