"""Unit tests for ScopeValidator — scope enforcement for pentest engagements."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.adapters.security.scope_validator import (
    ScopeRules,
    ScopeViolation,
    ScopeValidator,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_validator(
    allowed_cidrs: list[str] | None = None,
    allowed_domains: list[str] | None = None,
    excluded: list[str] | None = None,
) -> ScopeValidator:
    rules = ScopeRules(
        allowed_cidrs=allowed_cidrs or [],
        allowed_domains=allowed_domains or [],
        excluded=excluded or [],
    )
    return ScopeValidator(rules)


# ---------------------------------------------------------------------------
# IP validation
# ---------------------------------------------------------------------------


class TestValidateIp:
    def test_allows_ip_in_allowed_cidr(self) -> None:
        v = _make_validator(allowed_cidrs=["203.0.113.0/24"])
        v.validate_ip("203.0.113.10")  # should not raise

    def test_rejects_ip_outside_allowed_cidr(self) -> None:
        v = _make_validator(allowed_cidrs=["203.0.113.0/24"])
        with pytest.raises(ScopeViolation, match="not within any allowed CIDR"):
            v.validate_ip("198.51.100.1")

    def test_rejects_rfc1918_private_ip_10(self) -> None:
        v = _make_validator(allowed_cidrs=["0.0.0.0/0"])  # wide open, but blocked by hard-block
        with pytest.raises(ScopeViolation, match="hard-blocked"):
            v.validate_ip("10.0.0.1")

    def test_rejects_rfc1918_private_ip_192_168(self) -> None:
        v = _make_validator(allowed_cidrs=["0.0.0.0/0"])
        with pytest.raises(ScopeViolation, match="hard-blocked"):
            v.validate_ip("192.168.1.1")

    def test_rejects_rfc1918_private_ip_172_16(self) -> None:
        v = _make_validator(allowed_cidrs=["0.0.0.0/0"])
        with pytest.raises(ScopeViolation, match="hard-blocked"):
            v.validate_ip("172.16.0.1")

    def test_rejects_loopback(self) -> None:
        v = _make_validator(allowed_cidrs=["0.0.0.0/0"])
        with pytest.raises(ScopeViolation, match="hard-blocked"):
            v.validate_ip("127.0.0.1")

    def test_rejects_link_local(self) -> None:
        v = _make_validator(allowed_cidrs=["0.0.0.0/0"])
        with pytest.raises(ScopeViolation, match="hard-blocked"):
            v.validate_ip("169.254.1.1")

    def test_rejects_aws_metadata_ip(self) -> None:
        v = _make_validator(allowed_cidrs=["169.254.0.0/16"])
        # cloud metadata is blocked BEFORE scope check
        with pytest.raises(ScopeViolation, match="cloud metadata"):
            v.validate_ip("169.254.169.254")

    def test_rejects_azure_metadata_ip(self) -> None:
        v = _make_validator(allowed_cidrs=["168.63.0.0/16"])
        with pytest.raises(ScopeViolation, match="cloud metadata"):
            v.validate_ip("168.63.129.16")

    def test_rejects_explicitly_excluded_ip(self) -> None:
        v = _make_validator(
            allowed_cidrs=["203.0.113.0/24"],
            excluded=["203.0.113.5"],
        )
        with pytest.raises(ScopeViolation, match="explicitly excluded"):
            v.validate_ip("203.0.113.5")

    def test_rejects_ip_in_excluded_cidr(self) -> None:
        v = _make_validator(
            allowed_cidrs=["203.0.113.0/24"],
            excluded=["203.0.113.128/25"],
        )
        with pytest.raises(ScopeViolation, match="within excluded CIDR"):
            v.validate_ip("203.0.113.200")

    def test_rejects_invalid_ip_string(self) -> None:
        v = _make_validator(allowed_cidrs=["203.0.113.0/24"])
        with pytest.raises(ScopeViolation, match="Invalid IP address"):
            v.validate_ip("not-an-ip")

    def test_rejects_when_no_allowed_cidrs(self) -> None:
        v = _make_validator()
        with pytest.raises(ScopeViolation, match="No allowed CIDRs"):
            v.validate_ip("203.0.113.1")


# ---------------------------------------------------------------------------
# CIDR validation
# ---------------------------------------------------------------------------


class TestValidateCidr:
    def test_allows_subnet_of_allowed_cidr(self) -> None:
        v = _make_validator(allowed_cidrs=["203.0.113.0/24"])
        v.validate_cidr("203.0.113.0/28")  # should not raise

    def test_rejects_supernet_of_allowed_cidr(self) -> None:
        v = _make_validator(allowed_cidrs=["203.0.113.0/24"])
        with pytest.raises(ScopeViolation):
            v.validate_cidr("203.0.113.0/16")

    def test_rejects_cidr_overlapping_private_range(self) -> None:
        v = _make_validator(allowed_cidrs=["0.0.0.0/0"])
        with pytest.raises(ScopeViolation, match="hard-blocked"):
            v.validate_cidr("10.0.0.0/8")

    def test_rejects_invalid_cidr_string(self) -> None:
        v = _make_validator(allowed_cidrs=["203.0.113.0/24"])
        with pytest.raises(ScopeViolation, match="Invalid CIDR"):
            v.validate_cidr("not-a-cidr")


# ---------------------------------------------------------------------------
# Domain validation
# ---------------------------------------------------------------------------


class TestValidateDomain:
    def test_allows_explicitly_allowed_domain(self) -> None:
        v = _make_validator(allowed_domains=["example.com"])
        with patch("src.adapters.security.scope_validator._resolve_to_ips", return_value=[]):
            v.validate_domain("example.com")

    def test_allows_subdomain_of_allowed_domain(self) -> None:
        v = _make_validator(allowed_domains=["example.com"])
        with patch("src.adapters.security.scope_validator._resolve_to_ips", return_value=[]):
            v.validate_domain("sub.example.com")

    def test_rejects_explicitly_excluded_domain(self) -> None:
        v = _make_validator(
            allowed_domains=["example.com"],
            excluded=["staging.example.com"],
        )
        with pytest.raises(ScopeViolation, match="explicitly excluded"):
            v.validate_domain("staging.example.com")

    def test_rejects_domain_resolving_to_private_ip(self) -> None:
        import ipaddress

        v = _make_validator(allowed_cidrs=["203.0.113.0/24"])
        with patch(
            "src.adapters.security.scope_validator._resolve_to_ips",
            return_value=[ipaddress.ip_address("10.0.0.5")],
        ):
            with pytest.raises(ScopeViolation, match="hard-blocked"):
                v.validate_domain("internal.example.com")

    def test_rejects_domain_resolving_outside_allowed_cidrs(self) -> None:
        import ipaddress

        v = _make_validator(allowed_cidrs=["203.0.113.0/24"])
        with patch(
            "src.adapters.security.scope_validator._resolve_to_ips",
            return_value=[ipaddress.ip_address("198.51.100.1")],
        ):
            with pytest.raises(ScopeViolation):
                v.validate_domain("external.example.com")

    def test_allows_domain_resolving_to_allowed_cidr(self) -> None:
        import ipaddress

        v = _make_validator(allowed_cidrs=["203.0.113.0/24"])
        with patch(
            "src.adapters.security.scope_validator._resolve_to_ips",
            return_value=[ipaddress.ip_address("203.0.113.10")],
        ):
            v.validate_domain("target.example.com")  # should not raise

    def test_rejects_domain_that_cannot_be_resolved_and_not_allowed(self) -> None:
        v = _make_validator(allowed_cidrs=["203.0.113.0/24"])
        with patch(
            "src.adapters.security.scope_validator._resolve_to_ips",
            return_value=[],
        ):
            with pytest.raises(ScopeViolation, match="could not be resolved"):
                v.validate_domain("unresolvable.example.com")


# ---------------------------------------------------------------------------
# URL validation
# ---------------------------------------------------------------------------


class TestValidateUrl:
    def test_allows_url_with_allowed_ip(self) -> None:
        v = _make_validator(allowed_cidrs=["203.0.113.0/24"])
        v.validate_url("https://203.0.113.10/login")

    def test_rejects_url_with_private_ip(self) -> None:
        v = _make_validator(allowed_cidrs=["203.0.113.0/24"])
        with pytest.raises(ScopeViolation, match="hard-blocked"):
            v.validate_url("http://192.168.1.1/admin")

    def test_allows_url_with_allowed_domain(self) -> None:
        v = _make_validator(allowed_domains=["example.com"])
        with patch("src.adapters.security.scope_validator._resolve_to_ips", return_value=[]):
            v.validate_url("https://example.com/api/v1/users")

    def test_rejects_url_with_no_host(self) -> None:
        v = _make_validator(allowed_cidrs=["203.0.113.0/24"])
        with pytest.raises(ScopeViolation, match="Cannot extract host"):
            v.validate_url("not-a-url")

    def test_rejects_url_pointing_to_aws_metadata(self) -> None:
        v = _make_validator(allowed_cidrs=["169.254.0.0/16"])
        with pytest.raises(ScopeViolation, match="cloud metadata"):
            v.validate_url("http://169.254.169.254/latest/meta-data/")
