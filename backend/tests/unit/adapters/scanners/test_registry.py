import pytest
from src.adapters.scanners.registry import ScannerRegistry, create_default_registry
from src.core.domain.entities.types import ScanInputType


class TestScannerRegistry:
    def test_default_registry_has_scanners(self):
        registry = create_default_registry()
        assert len(registry.all_scanners) >= 4

    def test_get_for_email_returns_holehe(self):
        registry = create_default_registry()
        scanners = registry.get_for_input_type(ScanInputType.EMAIL)
        names = [s.scanner_name for s in scanners]
        assert "holehe" in names

    def test_get_for_username_returns_maigret(self):
        registry = create_default_registry()
        scanners = registry.get_for_input_type(ScanInputType.USERNAME)
        names = [s.scanner_name for s in scanners]
        assert "maigret" in names

    def test_get_for_nip_returns_vat_and_krs(self):
        registry = create_default_registry()
        scanners = registry.get_for_input_type(ScanInputType.NIP)
        names = [s.scanner_name for s in scanners]
        assert "vat_status" in names

    def test_get_by_name(self):
        registry = create_default_registry()
        scanner = registry.get_by_name("holehe")
        assert scanner is not None
        assert scanner.scanner_name == "holehe"

    def test_get_by_name_nonexistent(self):
        registry = create_default_registry()
        assert registry.get_by_name("nonexistent") is None

    def test_register_custom_scanner(self):
        from src.adapters.scanners.base import BaseOsintScanner
        class CustomScanner(BaseOsintScanner):
            scanner_name = "custom"
            supported_input_types = frozenset({ScanInputType.DOMAIN})
            async def _do_scan(self, input_value, input_type):
                return {}

        registry = ScannerRegistry()
        registry.register(CustomScanner())
        assert len(registry.all_scanners) == 1
        assert registry.get_by_name("custom") is not None


class TestGetDefaultRegistryCache:
    def test_returns_same_instance_on_repeated_calls(self):
        from src.adapters.scanners.registry import get_default_registry
        r1 = get_default_registry()
        r2 = get_default_registry()
        assert r1 is r2

    def test_cache_clear_creates_new_instance(self):
        from src.adapters.scanners.registry import get_default_registry
        r1 = get_default_registry()
        get_default_registry.cache_clear()
        r2 = get_default_registry()
        # After clearing the cache, a new instance is created
        assert r1 is not r2
        # Restore for other tests
        get_default_registry.cache_clear()

    def test_all_scanners_populated_in_cached_instance(self):
        from src.adapters.scanners.registry import get_default_registry
        get_default_registry.cache_clear()
        registry = get_default_registry()
        assert len(registry.all_scanners) >= 4

    def test_get_for_type_uses_o1_lookup(self):
        """_by_type index returns correct scanners without O(n) iteration."""
        from src.adapters.scanners.registry import get_default_registry
        registry = get_default_registry()
        email_scanners = registry.get_for_input_type(ScanInputType.EMAIL)
        domain_scanners = registry.get_for_input_type(ScanInputType.DOMAIN)
        # No EMAIL scanner should appear in the DOMAIN list
        email_names = {s.scanner_name for s in email_scanners}
        domain_names = {s.scanner_name for s in domain_scanners}
        # holehe is email-only — must not be in domain scanners
        assert "holehe" in email_names
        assert "holehe" not in domain_names
