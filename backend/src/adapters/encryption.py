"""Data encryption utilities for sensitive scan results.

PLACEHOLDER: In production, use cryptography.fernet with a master key
stored in a vault (HashiCorp Vault, AWS KMS, etc).
"""

import base64
import hashlib

import structlog

log = structlog.get_logger()


class DataEncryptor:
    """Encrypts and decrypts sensitive data using Fernet symmetric encryption.

    NOTE: This is a placeholder implementation. For production:
    1. Use a proper key management service (KMS)
    2. Rotate encryption keys periodically
    3. Use per-tenant keys for multi-tenant deployments
    """

    def __init__(self, master_key: str | None = None) -> None:
        self._key = master_key

    def encrypt(self, data: str) -> str:
        """Encrypt a string. Returns base64-encoded ciphertext."""
        if not self._key:
            return data  # No encryption if no key configured
        try:
            from cryptography.fernet import Fernet
            key = base64.urlsafe_b64encode(hashlib.sha256(self._key.encode()).digest())
            f = Fernet(key)
            return f.encrypt(data.encode()).decode()
        except ImportError:
            log.warning("cryptography not installed, returning plaintext")
            return data

    def decrypt(self, data: str) -> str:
        """Decrypt a base64-encoded ciphertext."""
        if not self._key:
            return data
        try:
            from cryptography.fernet import Fernet
            key = base64.urlsafe_b64encode(hashlib.sha256(self._key.encode()).digest())
            f = Fernet(key)
            return f.decrypt(data.encode()).decode()
        except Exception:
            return data
