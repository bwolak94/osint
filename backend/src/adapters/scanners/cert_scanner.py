"""Certificate Transparency scanner — discovers subdomains via crt.sh."""

from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Maximum number of certificate entries to process from crt.sh
_MAX_RESULTS = 100


class CertTransparencyScanner(BaseOsintScanner):
    """Queries crt.sh for Certificate Transparency logs to discover subdomains."""

    scanner_name = "cert_transparency"
    supported_input_types = frozenset({ScanInputType.DOMAIN})
    cache_ttl = 86400  # 24 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                "https://crt.sh/",
                params={"q": f"%.{input_value}", "output": "json"},
            )

            if resp.status_code == 404:
                return {
                    "domain": input_value,
                    "found": False,
                    "subdomains": [],
                    "extracted_identifiers": [],
                }

            resp.raise_for_status()
            entries = resp.json()

        # Collect unique subdomains from common_name and name_value fields
        subdomains: set[str] = set()
        for entry in entries[:_MAX_RESULTS]:
            for field in ("common_name", "name_value"):
                value = entry.get(field, "")
                # name_value can contain multiple domains separated by newlines
                for name in value.split("\n"):
                    name = name.strip().lower()
                    # Skip wildcards and empty entries
                    if name and not name.startswith("*") and input_value in name:
                        subdomains.add(name)

        sorted_subdomains = sorted(subdomains)

        identifiers: list[str] = []
        for subdomain in sorted_subdomains:
            identifiers.append(f"domain:{subdomain}")

        return {
            "domain": input_value,
            "found": bool(sorted_subdomains),
            "total_certs": len(entries),
            "unique_subdomains": len(sorted_subdomains),
            "subdomains": sorted_subdomains,
            "extracted_identifiers": identifiers,
        }
