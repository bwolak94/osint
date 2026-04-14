from dataclasses import dataclass
from uuid import UUID

from src.core.domain.events.base import DomainEvent


@dataclass(frozen=True)
class ScanCompleted(DomainEvent):
    """Raised when a scan finishes successfully."""
    scan_result_id: UUID = None  # type: ignore[assignment]
    investigation_id: UUID = None  # type: ignore[assignment]
    scanner_name: str = ""
    identifiers_found: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScanFailed(DomainEvent):
    """Raised when a scan encounters an error."""
    scan_result_id: UUID = None  # type: ignore[assignment]
    investigation_id: UUID = None  # type: ignore[assignment]
    scanner_name: str = ""
    error_message: str = ""
