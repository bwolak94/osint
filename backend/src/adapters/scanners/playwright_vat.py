"""VAT status scanner using the Polish Ministry of Finance API (Biala Lista)."""

from typing import Any

import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()


class VATStatusScanner(BaseOsintScanner):
    """Checks VAT registration status via the public MF API.

    This scanner uses a REST API (no browser needed) to check NIP status
    on the "Biala Lista" (white list of VAT payers).
    """

    scanner_name = "vat_status"
    supported_input_types = frozenset({ScanInputType.NIP})

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        try:
            import httpx
        except ImportError:
            return {"_stub": True, "error": "httpx not installed", "extracted_identifiers": []}

        from datetime import date
        today = date.today().isoformat()
        url = f"https://wl-api.mf.gov.pl/api/search/nip/{input_value}"
        params = {"date": today}

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        subject = data.get("result", {}).get("subject")
        if subject is None:
            return {
                "nip": input_value,
                "found": False,
                "extracted_identifiers": [],
            }

        bank_accounts = subject.get("accountNumbers", [])
        identifiers: list[str] = []
        for account in bank_accounts:
            identifiers.append(f"bank_account:{account}")
        if subject.get("name"):
            identifiers.append(f"company_name:{subject['name']}")

        return {
            "nip": input_value,
            "found": True,
            "name": subject.get("name"),
            "status_vat": subject.get("statusVat"),
            "regon": subject.get("regon"),
            "krs": subject.get("krs"),
            "residence_address": subject.get("residenceAddress"),
            "working_address": subject.get("workingAddress"),
            "bank_accounts": bank_accounts,
            "registration_date": subject.get("registrationLegalDate"),
            "extracted_identifiers": identifiers,
        }
