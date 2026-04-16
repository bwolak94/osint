"""Scanner registry — maps input types to available scanners."""

from src.adapters.scanners.base import BaseOsintScanner
from src.adapters.scanners.breach_scanner import BreachScanner
from src.adapters.scanners.cert_scanner import CertTransparencyScanner
from src.adapters.scanners.dns_scanner import DNSScanner
from src.adapters.scanners.facebook_scanner import FacebookScanner
from src.adapters.scanners.geoip_scanner import GeoIPScanner
from src.adapters.scanners.google_scanner import GoogleAccountScanner
from src.adapters.scanners.holehe_scanner import HoleheScanner
from src.adapters.scanners.instagram_scanner import InstagramScanner
from src.adapters.scanners.linkedin_scanner import LinkedInScanner
from src.adapters.scanners.maigret_scanner import MaigretScanner
from src.adapters.scanners.phone_scanner import PhoneScanner
from src.adapters.scanners.playwright_ceidg import PlaywrightCEIDGScanner
from src.adapters.scanners.playwright_krs import PlaywrightKRSScanner
from src.adapters.scanners.playwright_vat import VATStatusScanner
from src.adapters.scanners.shodan_scanner import ShodanScanner
from src.adapters.scanners.twitter_scanner import TwitterScanner
from src.adapters.scanners.virustotal_scanner import VirusTotalScanner
from src.adapters.scanners.whois_scanner import WhoisScanner
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
    registry.register(WhoisScanner())
    registry.register(DNSScanner())
    registry.register(ShodanScanner())
    registry.register(GeoIPScanner())
    registry.register(CertTransparencyScanner())
    registry.register(BreachScanner())
    registry.register(PhoneScanner())
    registry.register(VirusTotalScanner())
    registry.register(GoogleAccountScanner())
    registry.register(LinkedInScanner())
    registry.register(TwitterScanner())
    registry.register(FacebookScanner())
    registry.register(InstagramScanner())
    return registry


_default_registry: ScannerRegistry | None = None  # Reset on module reload


def get_default_registry() -> ScannerRegistry:
    """Return a cached singleton scanner registry."""
    global _default_registry
    if _default_registry is None:
        _default_registry = create_default_registry()
    return _default_registry
