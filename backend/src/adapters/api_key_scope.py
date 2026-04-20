"""Scoped API key enforcement for the OSINT platform."""

import hashlib
import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum

import structlog

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------


class KeyPermission(StrEnum):
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"


# Hierarchy: ADMIN implies WRITE implies READ.
_PERMISSION_RANK: dict[KeyPermission, int] = {
    KeyPermission.READ: 0,
    KeyPermission.WRITE: 1,
    KeyPermission.ADMIN: 2,
}


@dataclass
class APIKeyScope:
    """Full scope definition for an issued API key."""

    key_id: str
    owner_id: str
    permissions: list[KeyPermission]
    allowed_endpoints: list[str]  # regex patterns, e.g. ["/api/v1/investigations.*"]
    allowed_investigation_ids: list[str]  # empty list = unrestricted
    ip_allowlist: list[str]  # empty list = all IPs allowed
    rate_limit_per_minute: int = 60
    is_active: bool = True
    expires_at: str | None = None  # ISO-8601 datetime string


# ---------------------------------------------------------------------------
# Enforcer
# ---------------------------------------------------------------------------


class APIKeyScopeEnforcer:
    """Validates API key permissions against the incoming request context.

    All ``check_*`` methods are synchronous and side-effect-free so they can be
    used from both async FastAPI path operations and sync background tasks.
    """

    # ------------------------------------------------------------------
    # Individual constraint checks
    # ------------------------------------------------------------------

    def check_endpoint(self, scope: APIKeyScope, endpoint: str) -> bool:
        """Return ``True`` when *endpoint* matches at least one allowed pattern.

        An empty :attr:`~APIKeyScope.allowed_endpoints` list is treated as
        *allow-all* to support legacy keys created before endpoint scoping was
        introduced.
        """
        if not scope.allowed_endpoints:
            return True

        for pattern in scope.allowed_endpoints:
            try:
                if re.fullmatch(pattern, endpoint):
                    return True
            except re.error as exc:
                log.warning(
                    "api_key.invalid_endpoint_pattern",
                    pattern=pattern,
                    error=str(exc),
                )

        log.debug(
            "api_key.endpoint_denied",
            key_id=scope.key_id,
            endpoint=endpoint,
        )
        return False

    def check_investigation(
        self, scope: APIKeyScope, investigation_id: str
    ) -> bool:
        """Return ``True`` when *investigation_id* is within the allowed set.

        An empty :attr:`~APIKeyScope.allowed_investigation_ids` list means the
        key is not restricted to any particular investigation.
        """
        if not scope.allowed_investigation_ids:
            return True

        allowed = investigation_id in scope.allowed_investigation_ids
        if not allowed:
            log.debug(
                "api_key.investigation_denied",
                key_id=scope.key_id,
                investigation_id=investigation_id,
            )
        return allowed

    def check_ip(self, scope: APIKeyScope, client_ip: str) -> bool:
        """Return ``True`` when *client_ip* is in the allowlist.

        An empty :attr:`~APIKeyScope.ip_allowlist` means all IPs are permitted.
        Currently supports exact-match comparison only; CIDR support can be
        added by replacing the equality check with ``ipaddress`` lookups.
        """
        if not scope.ip_allowlist:
            return True

        allowed = client_ip in scope.ip_allowlist
        if not allowed:
            log.warning(
                "api_key.ip_denied",
                key_id=scope.key_id,
                client_ip=client_ip,
            )
        return allowed

    def check_permission(
        self, scope: APIKeyScope, required: KeyPermission
    ) -> bool:
        """Return ``True`` when the key carries at least *required* permission.

        ADMIN implies WRITE; WRITE implies READ.
        """
        required_rank = _PERMISSION_RANK[required]

        for perm in scope.permissions:
            if _PERMISSION_RANK.get(perm, -1) >= required_rank:
                return True

        log.debug(
            "api_key.permission_denied",
            key_id=scope.key_id,
            required=required,
            held=scope.permissions,
        )
        return False

    def check_expiry(self, scope: APIKeyScope) -> bool:
        """Return ``True`` when the key has not yet expired.

        Keys without an ``expires_at`` value never expire.
        """
        if scope.expires_at is None:
            return True

        try:
            expiry = datetime.fromisoformat(scope.expires_at)
        except ValueError as exc:
            log.error(
                "api_key.invalid_expiry_format",
                key_id=scope.key_id,
                expires_at=scope.expires_at,
                error=str(exc),
            )
            return False  # Treat malformed expiry as expired for safety.

        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)

        still_valid = datetime.now(timezone.utc) < expiry
        if not still_valid:
            log.warning("api_key.expired", key_id=scope.key_id, expires_at=scope.expires_at)
        return still_valid

    # ------------------------------------------------------------------
    # Aggregate validation
    # ------------------------------------------------------------------

    def validate_all(
        self,
        scope: APIKeyScope,
        endpoint: str,
        client_ip: str,
        investigation_id: str | None = None,
        required_permission: KeyPermission = KeyPermission.READ,
    ) -> tuple[bool, str]:
        """Run all constraint checks and return ``(allowed, denial_reason)``.

        Short-circuits on the first failed check so that the cheapest checks
        (active flag, expiry) are evaluated before the more expensive ones.

        Returns:
            A tuple of ``(True, "")`` on success, or
            ``(False, "<human-readable reason>")`` on failure.
        """
        if not scope.is_active:
            return False, "API key is inactive."

        if not self.check_expiry(scope):
            return False, "API key has expired."

        if not self.check_permission(scope, required_permission):
            return (
                False,
                f"API key lacks the required '{required_permission}' permission.",
            )

        if not self.check_ip(scope, client_ip):
            return False, f"Client IP '{client_ip}' is not in the allowlist."

        if not self.check_endpoint(scope, endpoint):
            return False, f"Endpoint '{endpoint}' is not permitted for this key."

        if investigation_id is not None and not self.check_investigation(
            scope, investigation_id
        ):
            return (
                False,
                f"Investigation '{investigation_id}' is not accessible with this key.",
            )

        log.info(
            "api_key.validated",
            key_id=scope.key_id,
            endpoint=endpoint,
            client_ip=client_ip,
        )
        return True, ""

    # ------------------------------------------------------------------
    # Key generation and hashing
    # ------------------------------------------------------------------

    def generate_key(self, length: int = 32) -> str:
        """Generate a cryptographically secure, URL-safe API key string.

        The caller is responsible for hashing the returned raw key before
        storing it in the database.

        Args:
            length: Number of random bytes used.  The resulting base64 string
                will be slightly longer than *length* characters.

        Returns:
            A URL-safe base64-encoded string with no padding characters.
        """
        import base64

        raw_bytes = secrets.token_bytes(length)
        key = base64.urlsafe_b64encode(raw_bytes).rstrip(b"=").decode()
        log.debug("api_key.generated", key_prefix=key[:8])
        return key

    def hash_key(self, raw_key: str) -> str:
        """Return the SHA-256 hex digest of *raw_key* for database storage.

        Only the hash is persisted; the plaintext key is shown to the user once
        at creation time and never stored.
        """
        digest = hashlib.sha256(raw_key.encode()).hexdigest()
        return digest
