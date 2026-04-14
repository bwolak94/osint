"""ScanResult entity — the output of a single scanner execution."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from src.core.domain.entities.types import ScanStatus


@dataclass
class ScanResult:
    """Mutable entity capturing the result of one scanner run against a seed input."""

    id: UUID
    investigation_id: UUID
    scanner_name: str
    input_value: str
    status: ScanStatus
    raw_data: dict[str, Any]
    extracted_identifiers: list[str]
    duration_ms: int
    created_at: datetime
    error_message: str | None = None

    # -- behaviour ----------------------------------------------------------

    def is_successful(self) -> bool:
        """True when the scan completed without errors."""
        return self.status is ScanStatus.SUCCESS

    def has_findings(self) -> bool:
        """True when the scan extracted at least one identifier."""
        return len(self.extracted_identifiers) > 0
