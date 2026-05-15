"""Scoped API key enforcement for the OSINT platform."""

import base64
import hashlib
import hmac
import ipaddress
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from functools import lru_cache

import structlog

from src.config import get_settings

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------


class KeyPermission(StrEnum):
    READ = "read"
    EXECUTE = "execute"  # Run scans — implies READ but not WRITE/ADMIN (#2)
    WRITE = "write"
    ADMIN = "admin"


# Hierarchy: ADMIN implies WRITE implies EXECUTE implies READ. (#2)
_PERMISSION_RANK: dict[KeyPermission, int] = {
    KeyPermission.READ: 0,
    KeyPermission.EXECUTE: 1,
    KeyPermission.WRITE: 2,
    KeyPermission.ADMIN: 3,
}


@dataclass
class APIKeyScope:
    """Full scope definition for an issued API key.

    List fields are converted to tuples in ``__post_init__`` to prevent
    accidental mutation of grant definitions after creation.
    """

    key_id: str
    owner_id: str
    permissions: tuple[KeyPermission, ...]
    allowed_endpoints: tuple[str, ...]  # regex patterns, e.g. ("/api/v1/investigations.*",)
    allowed_investigation_ids: tuple[str, ...]  # empty = unrestricted
    ip_allowlist: tuple[str, ...]  # empty = all IPs allowed; supports CIDR notation
    rate_limit_per_minute: int = 60
    is_active: bool = True
    expires_at: str | None = None  # ISO-8601 datetime string

    def __post_init__(self) -> None:
        # Coerce lists to tuples so the scope is effectively immutable.
        if isinstance(self.permissions, list):
            object.__setattr__(self, "permissions", tuple(self.permissions))
        if isinstance(self.allowed_endpoints, list):
            object.__setattr__(self, "allowed_endpoints", tuple(self.allowed_endpoints))
        if isinstance(self.allowed_investigation_ids, list):
            object.__setattr__(self, "allowed_investigation_ids", tuple(self.allowed_investigation_ids))
        if isinstance(self.ip_allowlist, list):
            object.__setattr__(self, "ip_allowlist", tuple(self.ip_allowlist))


# ---------------------------------------------------------------------------
# Compiled regex cache — avoids re-compiling the same pattern on every request.
# ---------------------------------------------------------------------------

@lru_cache(maxsize=256)
def _compile_pattern(pattern: str) -> re.Pattern | None:
    """Return a compiled pattern, or None if *pattern* is invalid regex."""
    try:
        return re.compile(pattern)
    except re.error as exc:
        log.warning("api_key.invalid_endpoint_pattern", pattern=pattern, error=str(exc))
        return None


# ---------------------------------------------------------------------------
# Parsed IP/network cache — avoids re-parsing allowlist entries per request. (#1)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1024)
def _parse_network_entry(
    entry: str,
) -> ipaddress.IPv4Network | ipaddress.IPv6Network | ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """Parse and cache a CIDR or exact-address allowlist entry.

    Parsing is expensive relative to the actual address comparison, so we cache
    the result keyed on the raw string.  lru_cache is safe here because allowlist
    entries are immutable once an APIKeyScope is constructed.
    """
    try:
        if "/" in entry:
            return ipaddress.ip_network(entry, strict=False)
        return ipaddress.ip_address(entry)
    except ValueError as exc:
        log.warning("api_key.invalid_allowlist_entry", entry=entry, error=str(exc))
        return None


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

        An empty :attr:`~APIKeyScope.allowed_endpoints` tuple is treated as
        *allow-all* to support legacy keys created before endpoint scoping was
        introduced.  Regex patterns are compiled once and cached.
        """
        if not scope.allowed_endpoints:
            return True

        for pattern in scope.allowed_endpoints:
            compiled = _compile_pattern(pattern)
            if compiled is not None and compiled.fullmatch(endpoint):
                return True

        # Security event — use WARNING so it appears in production log aggregators. (#22)
        log.warning("api_key.endpoint_denied", key_id=scope.key_id, endpoint=endpoint)
        return False

    def check_investigation(self, scope: APIKeyScope, investigation_id: str) -> bool:
        """Return ``True`` when *investigation_id* is within the allowed set.

        An empty :attr:`~APIKeyScope.allowed_investigation_ids` tuple means the
        key is not restricted to any particular investigation.
        """
        if not scope.allowed_investigation_ids:
            return True

        allowed = investigation_id in scope.allowed_investigation_ids
        if not allowed:
            # Security event — WARNING level for auditability. (#22)
            log.warning(
                "api_key.investigation_denied",
                key_id=scope.key_id,
                investigation_id=investigation_id,
            )
        return allowed

    def check_ip(self, scope: APIKeyScope, client_ip: str) -> bool:
        """Return ``True`` when *client_ip* is in the allowlist.

        An empty :attr:`~APIKeyScope.ip_allowlist` means all IPs are permitted.
        Supports both exact-match addresses and CIDR notation (e.g. ``192.168.1.0/24``).
        Parsed networks are cached via ``_parse_network_entry`` (#1).
        """
        if not scope.ip_allowlist:
            return True

        try:
            client_addr = ipaddress.ip_address(client_ip)
        except ValueError:
            log.warning("api_key.invalid_client_ip", key_id=scope.key_id, client_ip=client_ip)
            return False

        for entry in scope.ip_allowlist:
            parsed = _parse_network_entry(entry)  # cached — no re-parsing per request (#1)
            if parsed is None:
                continue
            if isinstance(parsed, (ipaddress.IPv4Network, ipaddress.IPv6Network)):
                if client_addr in parsed:
                    return True
            else:
                if client_addr == parsed:
                    return True

        log.warning("api_key.ip_denied", key_id=scope.key_id, client_ip=client_ip)
        return False

    def check_permission(self, scope: APIKeyScope, required: KeyPermission) -> bool:
        """Return ``True`` when the key carries at least *required* permission.

        ADMIN implies WRITE; WRITE implies EXECUTE; EXECUTE implies READ. (#2)
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

        Checks are ordered cheapest-first (#19):
          is_active → expiry → IP allowlist → permission → endpoint → investigation

        IP is checked before permission because a blocked IP should never learn
        which permissions are missing (avoids information leakage).

        Returns:
            A tuple of ``(True, "")`` on success, or
            ``(False, "<human-readable reason>")`` on failure.
        """
        if not scope.is_active:
            return False, "API key is inactive."

        if not self.check_expiry(scope):
            return False, "API key has expired."

        # IP check before permission — blocked IPs should not learn about scope. (#19)
        if not self.check_ip(scope, client_ip):
            return False, f"Client IP '{client_ip}' is not in the allowlist."

        if not self.check_permission(scope, required_permission):
            return (
                False,
                f"API key lacks the required '{required_permission}' permission.",
            )

        if not self.check_endpoint(scope, endpoint):
            return False, f"Endpoint '{endpoint}' is not permitted for this key."

        if investigation_id is not None and not self.check_investigation(
            scope, investigation_id
        ):
            return (
                False,
                f"Investigation '{investigation_id}' is not accessible with this key.",
            )

        log.debug(
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
        raw_bytes = secrets.token_bytes(length)
        key = base64.urlsafe_b64encode(raw_bytes).rstrip(b"=").decode()
        log.debug("api_key.generated", key_prefix=key[:8])
        return key

    def hash_key(self, raw_key: str) -> str:
        """Return HMAC-SHA256 hex digest of *raw_key* for database storage. (#3)

        Uses the JWT secret as the HMAC key so the hash is application-scoped.
        This prevents preimage attacks on low-entropy keys and length-extension
        attacks that affect raw SHA-256.  Only the digest is persisted; the
        plaintext key is shown to the user once at creation time and never stored.
        """
        settings = get_settings()
        return hmac.new(
            settings.jwt_secret_key.encode(),
            raw_key.encode(),
            hashlib.sha256,
        ).hexdigest()
