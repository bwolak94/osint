"""Shared hosting scanner — discovers co-hosted domains via reverse IP lookup."""

import socket
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_HACKERTARGET_URL = "https://api.hackertarget.com/reverseiplookup/"


def _risk_level(count: int) -> str:
    if count <= 5:
        return "low"
    if count <= 50:
        return "medium"
    return "high"


class SharedHostingScanner(BaseOsintScanner):
    """Identifies co-hosted domains sharing the same IP to assess shared-hosting risk."""

    scanner_name = "shared_hosting"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.IP_ADDRESS})
    cache_ttl = 43200  # 12 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        # Resolve domain to IP if needed
        ip: str = input_value
        if input_type == ScanInputType.DOMAIN:
            try:
                ip = socket.gethostbyname(input_value)
            except OSError:
                return {
                    "target": input_value,
                    "found": False,
                    "ip": None,
                    "co_hosted_domains": [],
                    "risk_level": "low",
                    "error": "Could not resolve domain to IP",
                    "extracted_identifiers": [],
                }

        co_hosted: list[str] = []
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(_HACKERTARGET_URL, params={"q": ip})
                if resp.status_code == 200:
                    text = resp.text.strip()
                    if "error" not in text.lower() and "api count" not in text.lower():
                        co_hosted = [line.strip() for line in text.splitlines() if line.strip()]
        except Exception as exc:
            log.warning("shared_hosting reverse IP failed", error=str(exc))

        identifiers = [f"ip:{ip}"] + [f"domain:{d}" for d in co_hosted[:20]]

        return {
            "target": input_value,
            "found": len(co_hosted) > 0,
            "ip": ip,
            "co_hosted_domains": co_hosted,
            "co_hosted_count": len(co_hosted),
            "risk_level": _risk_level(len(co_hosted)),
            "extracted_identifiers": identifiers,
        }
