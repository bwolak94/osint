"""Celery tasks for OSINT scanning.

These are thin wrappers around scanner adapters. They do NOT contain
business logic — only Celery orchestration concerns (retry, logging, serialization).
Tasks return only scan_id + status, never large raw data (that stays in PostgreSQL).
"""

import asyncio
import structlog
from uuid import UUID

from src.workers.celery_app import celery_app

log = structlog.get_logger()


def _run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, name="scanners.holehe", max_retries=3, queue="light")
def holehe_scan_task(self, scan_id: str, email: str, investigation_id: str) -> dict:
    """Run a Holehe email scan."""
    try:
        from src.adapters.scanners.holehe_scanner import HoleheScanner
        from src.core.domain.entities.types import ScanInputType

        scanner = HoleheScanner()
        result = _run_async(scanner.scan(email, ScanInputType.EMAIL, investigation_id=UUID(investigation_id)))

        log.info("Holehe scan completed", scan_id=scan_id, status=result.status.value)
        return {"scan_id": scan_id, "status": result.status.value, "findings_count": len(result.extracted_identifiers)}

    except Exception as exc:
        log.error("Holehe scan failed", scan_id=scan_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@celery_app.task(bind=True, name="scanners.maigret", max_retries=3, queue="light")
def maigret_scan_task(self, scan_id: str, username: str, investigation_id: str) -> dict:
    """Run a Maigret username scan."""
    try:
        from src.adapters.scanners.maigret_scanner import MaigretScanner
        from src.core.domain.entities.types import ScanInputType

        scanner = MaigretScanner()
        result = _run_async(scanner.scan(username, ScanInputType.USERNAME, investigation_id=UUID(investigation_id)))

        log.info("Maigret scan completed", scan_id=scan_id, status=result.status.value)
        return {"scan_id": scan_id, "status": result.status.value, "findings_count": len(result.extracted_identifiers)}

    except Exception as exc:
        log.error("Maigret scan failed", scan_id=scan_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@celery_app.task(bind=True, name="scanners.vat", max_retries=3, queue="light")
def vat_scan_task(self, scan_id: str, nip: str, investigation_id: str) -> dict:
    """Run a VAT (Biala Lista) scan."""
    try:
        from src.adapters.scanners.playwright_vat import VATStatusScanner
        from src.core.domain.entities.types import ScanInputType

        scanner = VATStatusScanner()
        result = _run_async(scanner.scan(nip, ScanInputType.NIP, investigation_id=UUID(investigation_id)))

        log.info("VAT scan completed", scan_id=scan_id, status=result.status.value)
        return {"scan_id": scan_id, "status": result.status.value, "findings_count": len(result.extracted_identifiers)}

    except Exception as exc:
        log.error("VAT scan failed", scan_id=scan_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@celery_app.task(bind=True, name="scanners.playwright", max_retries=2, queue="heavy")
def playwright_scan_task(self, scan_id: str, query: str, input_type: str, scanner_name: str, investigation_id: str) -> dict:
    """Run a Playwright-based scan (KRS, CEIDG, etc.).

    Runs on the 'heavy' queue with limited concurrency.
    """
    try:
        from src.adapters.scanners.registry import create_default_registry
        from src.core.domain.entities.types import ScanInputType

        registry = create_default_registry()
        scanner = registry.get_by_name(scanner_name)
        if scanner is None:
            return {"scan_id": scan_id, "status": "failed", "error": f"Unknown scanner: {scanner_name}"}

        scan_input_type = ScanInputType(input_type)
        result = _run_async(scanner.scan(query, scan_input_type, investigation_id=UUID(investigation_id)))

        log.info("Playwright scan completed", scan_id=scan_id, scanner=scanner_name, status=result.status.value)
        return {"scan_id": scan_id, "status": result.status.value, "findings_count": len(result.extracted_identifiers)}

    except Exception as exc:
        log.error("Playwright scan failed", scan_id=scan_id, scanner=scanner_name, error=str(exc))
        raise self.retry(exc=exc, countdown=120 * (2 ** self.request.retries))
