"""Holehe scanner — checks email registration across 120+ services via password recovery endpoints."""

import asyncio
from typing import Any

import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()


class HoleheScanner(BaseOsintScanner):
    """Checks if an email is registered on various online services.

    Uses the holehe library which probes password recovery endpoints.
    Does NOT trigger any notifications to the email owner.
    """

    scanner_name = "holehe"
    supported_input_types = frozenset({ScanInputType.EMAIL})

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        try:
            import holehe.core as holehe_core

            out: list[dict[str, Any]] = []
            await holehe_core.import_from_web(input_value, out)

            registered = [r for r in out if r.get("exists") is True]
            services = [r["name"] for r in registered]

            # Extract partial recovery info if available
            partial_phone = None
            backup_email = None
            for r in registered:
                if r.get("phoneNumber"):
                    partial_phone = r["phoneNumber"]
                if r.get("emailrecovery"):
                    backup_email = r["emailrecovery"]

            return {
                "registered_on": services,
                "registered_count": len(services),
                "total_checked": len(out),
                "partial_phone": partial_phone,
                "backup_email": backup_email,
                "raw_results": out,
                "extracted_identifiers": self._build_identifiers(services, backup_email),
            }
        except ImportError:
            log.warning("holehe library not installed, returning stub results")
            return {
                "registered_on": [],
                "registered_count": 0,
                "total_checked": 0,
                "partial_phone": None,
                "backup_email": None,
                "raw_results": [],
                "extracted_identifiers": [],
                "_stub": True,
            }

    def _build_identifiers(self, services: list[str], backup_email: str | None) -> list[str]:
        """Build a list of new identifiers discovered during the scan."""
        identifiers: list[str] = []
        # Each service where the email is registered is a potential username source
        for service in services:
            identifiers.append(f"service:{service}")
        if backup_email:
            identifiers.append(f"email:{backup_email}")
        return identifiers
