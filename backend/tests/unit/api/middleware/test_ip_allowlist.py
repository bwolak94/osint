"""Tests for IP allowlist middleware."""
import pytest

from src.api.middleware.ip_allowlist import IPAllowlistMiddleware


class TestIPAllowlistMiddleware:
    def test_init_with_valid_ips(self):
        mw = IPAllowlistMiddleware(app=None, allowed_ips=["192.168.1.0/24", "10.0.0.1"], enabled=True)
        assert len(mw.allowed_networks) == 2
        assert mw.enabled is True

    def test_init_disabled(self):
        mw = IPAllowlistMiddleware(app=None, enabled=False)
        assert mw.enabled is False

    def test_init_with_invalid_ip(self):
        mw = IPAllowlistMiddleware(app=None, allowed_ips=["invalid", "10.0.0.0/8"], enabled=True)
        assert len(mw.allowed_networks) == 1
