"""Scanner registry — maps input types to available scanners."""

from src.adapters.scanners.base import BaseOsintScanner
from src.adapters.scanners.holehe_scanner import HoleheScanner
from src.adapters.scanners.maigret_scanner import MaigretScanner
from src.adapters.scanners.playwright_ceidg import PlaywrightCEIDGScanner
from src.adapters.scanners.playwright_krs import PlaywrightKRSScanner
from src.adapters.scanners.playwright_vat import VATStatusScanner
from src.core.domain.entities.types import ScanInputType


class ScannerRegistry:
    """Central registry of all available OSINT scanners.

    Provides lookup by input type so the orchestrator can automatically
    select the right scanners for a given seed input.
    """

    def __init__(self) -> None:
        self._scanners: list[BaseOsintScanner] = []

    def register(self, scanner: BaseOsintScanner) -> None:
        self._scanners.append(scanner)

    def get_for_input_type(self, input_type: ScanInputType) -> list[BaseOsintScanner]:
        return [s for s in self._scanners if s.supports(input_type)]

    def get_by_name(self, name: str) -> BaseOsintScanner | None:
        for s in self._scanners:
            if s.scanner_name == name:
                return s
        return None

    @property
    def all_scanners(self) -> list[BaseOsintScanner]:
        return list(self._scanners)


def create_default_registry() -> ScannerRegistry:
    """Create a registry with all built-in scanners."""
    registry = ScannerRegistry()
    registry.register(HoleheScanner())
    registry.register(MaigretScanner())
    registry.register(PlaywrightKRSScanner())
    registry.register(PlaywrightCEIDGScanner())
    registry.register(VATStatusScanner())
    return registry
