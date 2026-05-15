"""Unit tests for APIKeyScopeEnforcer.

Covers: permission hierarchy, CIDR IP matching, endpoint regex, expiry,
investigation restriction, and the aggregate validate_all path.
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.adapters.api_key_scope import APIKeyScope, APIKeyScopeEnforcer, KeyPermission


def _make_scope(**overrides) -> APIKeyScope:
    defaults = dict(
        key_id="test-key",
        owner_id="user-1",
        permissions=(KeyPermission.READ,),
        allowed_endpoints=(),
        allowed_investigation_ids=(),
        ip_allowlist=(),
        rate_limit_per_minute=60,
        is_active=True,
        expires_at=None,
    )
    defaults.update(overrides)
    return APIKeyScope(**defaults)


enforcer = APIKeyScopeEnforcer()


# ---------------------------------------------------------------------------
# Permission hierarchy
# ---------------------------------------------------------------------------

class TestCheckPermission:
    def test_read_key_grants_read(self):
        scope = _make_scope(permissions=(KeyPermission.READ,))
        assert enforcer.check_permission(scope, KeyPermission.READ)

    def test_read_key_denies_write(self):
        scope = _make_scope(permissions=(KeyPermission.READ,))
        assert not enforcer.check_permission(scope, KeyPermission.WRITE)

    def test_write_key_grants_read(self):
        scope = _make_scope(permissions=(KeyPermission.WRITE,))
        assert enforcer.check_permission(scope, KeyPermission.READ)

    def test_write_key_grants_write(self):
        scope = _make_scope(permissions=(KeyPermission.WRITE,))
        assert enforcer.check_permission(scope, KeyPermission.WRITE)

    def test_write_key_denies_admin(self):
        scope = _make_scope(permissions=(KeyPermission.WRITE,))
        assert not enforcer.check_permission(scope, KeyPermission.ADMIN)

    def test_admin_key_grants_all(self):
        scope = _make_scope(permissions=(KeyPermission.ADMIN,))
        assert enforcer.check_permission(scope, KeyPermission.READ)
        assert enforcer.check_permission(scope, KeyPermission.WRITE)
        assert enforcer.check_permission(scope, KeyPermission.ADMIN)


# ---------------------------------------------------------------------------
# IP allowlist — exact match and CIDR
# ---------------------------------------------------------------------------

class TestCheckIp:
    def test_empty_allowlist_allows_all(self):
        scope = _make_scope(ip_allowlist=())
        assert enforcer.check_ip(scope, "1.2.3.4")

    def test_exact_match_allowed(self):
        scope = _make_scope(ip_allowlist=("192.168.1.1",))
        assert enforcer.check_ip(scope, "192.168.1.1")

    def test_exact_match_denied(self):
        scope = _make_scope(ip_allowlist=("192.168.1.1",))
        assert not enforcer.check_ip(scope, "192.168.1.2")

    def test_cidr_range_allowed(self):
        scope = _make_scope(ip_allowlist=("10.0.0.0/8",))
        assert enforcer.check_ip(scope, "10.42.0.1")

    def test_cidr_range_denied(self):
        scope = _make_scope(ip_allowlist=("10.0.0.0/8",))
        assert not enforcer.check_ip(scope, "172.16.0.1")

    def test_invalid_client_ip_denied(self):
        scope = _make_scope(ip_allowlist=("10.0.0.0/8",))
        assert not enforcer.check_ip(scope, "not-an-ip")


# ---------------------------------------------------------------------------
# Endpoint regex
# ---------------------------------------------------------------------------

class TestCheckEndpoint:
    def test_empty_allowed_endpoints_allows_all(self):
        scope = _make_scope(allowed_endpoints=())
        assert enforcer.check_endpoint(scope, "/api/v1/anything")

    def test_pattern_match(self):
        scope = _make_scope(allowed_endpoints=(r"/api/v1/investigations.*",))
        assert enforcer.check_endpoint(scope, "/api/v1/investigations/123")

    def test_pattern_no_match(self):
        scope = _make_scope(allowed_endpoints=(r"/api/v1/investigations.*",))
        assert not enforcer.check_endpoint(scope, "/api/v1/scanners")

    def test_invalid_regex_is_skipped_not_raised(self):
        scope = _make_scope(allowed_endpoints=(r"[invalid",))
        assert not enforcer.check_endpoint(scope, "/any")

    def test_regex_compiled_once(self):
        """Calling check_endpoint twice for the same pattern should hit the LRU cache."""
        from src.adapters.api_key_scope import _compile_pattern
        _compile_pattern.cache_clear()
        scope = _make_scope(allowed_endpoints=(r"/api/v1/.*",))
        enforcer.check_endpoint(scope, "/api/v1/foo")
        enforcer.check_endpoint(scope, "/api/v1/bar")
        info = _compile_pattern.cache_info()
        assert info.hits >= 1


# ---------------------------------------------------------------------------
# Expiry
# ---------------------------------------------------------------------------

class TestCheckExpiry:
    def test_no_expiry_never_expires(self):
        scope = _make_scope(expires_at=None)
        assert enforcer.check_expiry(scope)

    def test_future_expiry_valid(self):
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        scope = _make_scope(expires_at=future)
        assert enforcer.check_expiry(scope)

    def test_past_expiry_invalid(self):
        past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        scope = _make_scope(expires_at=past)
        assert not enforcer.check_expiry(scope)

    def test_malformed_expiry_treated_as_expired(self):
        scope = _make_scope(expires_at="not-a-date")
        assert not enforcer.check_expiry(scope)


# ---------------------------------------------------------------------------
# Investigation restriction
# ---------------------------------------------------------------------------

class TestCheckInvestigation:
    def test_empty_list_allows_all(self):
        scope = _make_scope(allowed_investigation_ids=())
        assert enforcer.check_investigation(scope, "any-id")

    def test_allowed_id(self):
        scope = _make_scope(allowed_investigation_ids=("inv-1",))
        assert enforcer.check_investigation(scope, "inv-1")

    def test_denied_id(self):
        scope = _make_scope(allowed_investigation_ids=("inv-1",))
        assert not enforcer.check_investigation(scope, "inv-2")


# ---------------------------------------------------------------------------
# Aggregate validate_all
# ---------------------------------------------------------------------------

class TestValidateAll:
    def test_fully_valid_key_passes(self):
        scope = _make_scope()
        ok, reason = enforcer.validate_all(scope, "/api/v1/test", "127.0.0.1")
        assert ok
        assert reason == ""

    def test_inactive_key_fails(self):
        scope = _make_scope(is_active=False)
        ok, reason = enforcer.validate_all(scope, "/api/v1/test", "127.0.0.1")
        assert not ok
        assert "inactive" in reason.lower()

    def test_expired_key_fails(self):
        past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        scope = _make_scope(expires_at=past)
        ok, reason = enforcer.validate_all(scope, "/api/v1/test", "127.0.0.1")
        assert not ok
        assert "expired" in reason.lower()

    def test_wrong_permission_fails(self):
        scope = _make_scope(permissions=(KeyPermission.READ,))
        ok, reason = enforcer.validate_all(
            scope, "/api/v1/test", "127.0.0.1", required_permission=KeyPermission.WRITE
        )
        assert not ok
        assert "permission" in reason.lower()

    def test_ip_not_in_allowlist_fails(self):
        scope = _make_scope(ip_allowlist=("10.0.0.0/8",))
        ok, reason = enforcer.validate_all(scope, "/api/v1/test", "1.2.3.4")
        assert not ok
        assert "1.2.3.4" in reason

    def test_endpoint_not_allowed_fails(self):
        scope = _make_scope(allowed_endpoints=(r"/api/v1/investigations.*",))
        ok, reason = enforcer.validate_all(scope, "/api/v1/scanners", "127.0.0.1")
        assert not ok
        assert "/api/v1/scanners" in reason


# ---------------------------------------------------------------------------
# Key generation
# ---------------------------------------------------------------------------

class TestKeyGeneration:
    def test_generate_key_returns_url_safe_string(self):
        key = enforcer.generate_key()
        # URL-safe base64 uses [-_A-Za-z0-9] only (no padding =)
        assert all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for c in key)

    def test_generate_key_unique(self):
        keys = {enforcer.generate_key() for _ in range(50)}
        assert len(keys) == 50

    def test_hash_key_is_sha256_hex(self):
        raw = "my-api-key"
        digest = enforcer.hash_key(raw)
        assert len(digest) == 64
        assert all(c in "0123456789abcdef" for c in digest)

    def test_hash_key_deterministic(self):
        raw = "my-api-key"
        assert enforcer.hash_key(raw) == enforcer.hash_key(raw)


# ---------------------------------------------------------------------------
# Immutability
# ---------------------------------------------------------------------------

class TestImmutability:
    def test_list_permissions_coerced_to_tuple(self):
        scope = APIKeyScope(
            key_id="k",
            owner_id="u",
            permissions=[KeyPermission.READ],  # type: ignore[arg-type]
            allowed_endpoints=[],  # type: ignore[arg-type]
            allowed_investigation_ids=[],  # type: ignore[arg-type]
            ip_allowlist=[],  # type: ignore[arg-type]
        )
        assert isinstance(scope.permissions, tuple)
        assert isinstance(scope.allowed_endpoints, tuple)
        assert isinstance(scope.allowed_investigation_ids, tuple)
        assert isinstance(scope.ip_allowlist, tuple)
