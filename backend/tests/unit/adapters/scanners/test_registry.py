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
