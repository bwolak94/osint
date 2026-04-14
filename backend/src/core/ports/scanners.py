from typing import Protocol

from src.core.domain.entities.types import ScanInputType
from src.core.domain.entities.scan_result import ScanResult


class IOsintScanner(Protocol):
    @property
    def scanner_name(self) -> str: ...

    async def scan(self, input_value: str, input_type: ScanInputType) -> ScanResult: ...
    def supports(self, input_type: ScanInputType) -> bool: ...
