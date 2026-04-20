"""DNS scanner — resolves DNS records for a domain."""

import asyncio
import socket
from typing import Any

import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()


class DNSScanner(BaseOsintScanner):
    """Resolves A, MX, NS, and TXT records for a domain."""

    scanner_name = "dns_lookup"
    supported_input_types = frozenset({ScanInputType.DOMAIN})
    cache_ttl = 3600  # 1 hour — DNS changes frequently

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        try:
            import httpx

            records: dict[str, list[str]] = {"A": [], "MX": [], "NS": [], "TXT": []}

            # Use Google DNS-over-HTTPS for reliable resolution
            async with httpx.AsyncClient(timeout=10) as client:
                for rtype in ["A", "MX", "NS", "TXT"]:
                    try:
                        resp = await client.get(
                            "https://dns.google/resolve",
                            params={"name": input_value, "type": rtype},
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            for answer in data.get("Answer", []):
                                records[rtype].append(answer.get("data", ""))
                    except Exception:
                        pass

            identifiers = []
            for ip in records["A"]:
                identifiers.append(f"ip:{ip}")
            for mx in records["MX"]:
                parts = mx.strip().split()
                if len(parts) >= 2:
                    identifiers.append(f"domain:{parts[-1].rstrip('.')}")
            for ns in records["NS"]:
                identifiers.append(f"nameserver:{ns.rstrip('.')}")

            return {
                "domain": input_value,
                "found": bool(records["A"]),
                "records": records,
                "a_records": records["A"],
                "mx_records": records["MX"],
                "ns_records": records["NS"],
                "txt_records": records["TXT"],
                "extracted_identifiers": identifiers,
            }
        except ImportError:
            return {"domain": input_value, "found": False, "records": {}, "extracted_identifiers": [], "_stub": True}
        except Exception as e:
            log.error("DNS scan error", error=str(e))
            raise
