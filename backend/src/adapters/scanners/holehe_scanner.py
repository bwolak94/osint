"""Holehe scanner — checks email registration across 120+ services via password recovery endpoints."""

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
            import trio
            import httpx
            from holehe.core import import_submodules, get_functions
            import holehe.modules

            modules = import_submodules(holehe.modules)
            fns = get_functions(modules)

            out: list[dict[str, Any]] = []

            async def _run() -> None:
                async with httpx.AsyncClient(timeout=15) as client:
                    for fn in fns:
                        try:
                            await fn(input_value, client, out)
                        except Exception:
                            pass

            trio.run(_run)

            registered = [r for r in out if r.get("exists") is True]
            services = [r.get("name", "") for r in registered]

            partial_phone = None
            backup_email = None
            for r in registered:
                if r.get("phoneNumber"):
                    partial_phone = r["phoneNumber"]
                if r.get("emailrecovery"):
                    backup_email = r["emailrecovery"]

            return {
                "email": input_value,
                "registered_on": services,
                "registered_count": len(services),
                "total_checked": len(out),
                "partial_phone": partial_phone,
                "backup_email": backup_email,
                "extracted_identifiers": self._build_identifiers(services, backup_email),
            }
        except ImportError as e:
            log.warning("holehe not available", error=str(e))
            return {
                "registered_on": [],
                "registered_count": 0,
                "total_checked": 0,
                "extracted_identifiers": [],
                "_stub": True,
            }
        except Exception as e:
            log.error("holehe scan error", error=str(e))
            raise

    def _build_identifiers(self, services: list[str], backup_email: str | None) -> list[str]:
        identifiers: list[str] = []
        for service in services:
            identifiers.append(f"service:{service}")
        if backup_email:
            identifiers.append(f"email:{backup_email}")
        return identifiers
