"""Blockchair scanner — multi-chain crypto address analysis."""

import re
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_BASE_URL = "https://api.blockchair.com"

# Address format detection patterns
_BTC_RE = re.compile(r"^(1|3|bc1)[a-zA-Z0-9]{6,87}$")
_ETH_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
_LTC_RE = re.compile(r"^[LM][a-zA-Z0-9]{26,33}$")
_BCH_RE = re.compile(r"^(1[a-zA-Z0-9]{25,33}|bitcoincash:q[a-z0-9]{41})$")
_DOGE_RE = re.compile(r"^D[a-zA-Z0-9]{25,34}$")
_TRX_RE = re.compile(r"^T[a-zA-Z0-9]{33}$")


def _detect_chain(address: str) -> str | None:
    """Return the Blockchair chain slug for a given address, or None if unrecognised."""
    if _ETH_RE.match(address):
        return "ethereum"
    if _TRX_RE.match(address):
        return "tron"
    if _DOGE_RE.match(address):
        return "dogecoin"
    if _LTC_RE.match(address):
        return "litecoin"
    if _BCH_RE.match(address):
        return "bitcoin-cash"
    if _BTC_RE.match(address):
        return "bitcoin"
    return None


class BlockchairScanner(BaseOsintScanner):
    scanner_name = "blockchair"
    supported_input_types = frozenset({ScanInputType.IP_ADDRESS})
    cache_ttl = 300

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        chain = _detect_chain(input_value)
        if chain is None:
            return {
                "input": input_value,
                "found": False,
                "error": "Unrecognised crypto address format",
                "extracted_identifiers": [],
            }
        async with httpx.AsyncClient(timeout=20) as client:
            return await self._fetch_address(client, chain, input_value)

    async def _fetch_address(
        self, client: httpx.AsyncClient, chain: str, address: str
    ) -> dict[str, Any]:
        url = f"{_BASE_URL}/{chain}/dashboards/address/{address}"
        try:
            resp = await client.get(url, params={"key": ""})
            if resp.status_code == 429:
                return {
                    "input": address,
                    "found": False,
                    "error": "Blockchair rate limit exceeded",
                    "extracted_identifiers": [],
                }
            if resp.status_code != 200:
                return {
                    "input": address,
                    "found": False,
                    "error": f"Blockchair API error: {resp.status_code}",
                    "extracted_identifiers": [],
                }
            data = resp.json()
        except Exception as exc:
            log.warning("Blockchair fetch failed", chain=chain, address=address, error=str(exc))
            return {
                "input": address,
                "found": False,
                "error": str(exc),
                "extracted_identifiers": [],
            }

        addr_data = data.get("data", {}).get(address, {})
        if not addr_data:
            return {
                "input": address,
                "found": False,
                "chain": chain,
                "extracted_identifiers": [],
            }

        addr_info = addr_data.get("address", {})
        tags = data.get("context", {}).get("tags", [])

        # Normalise balance — Blockchair returns satoshis/wei depending on chain
        balance_raw = addr_info.get("balance", 0)
        received_raw = addr_info.get("received", 0)
        sent_raw = addr_info.get("spent", 0)
        divisor = self._chain_divisor(chain)

        return {
            "input": address,
            "found": True,
            "chain": chain,
            "address": address,
            "balance": balance_raw / divisor,
            "total_received": received_raw / divisor,
            "total_sent": sent_raw / divisor,
            "transaction_count": addr_info.get("transaction_count", 0),
            "first_seen": addr_info.get("first_seen_receiving", ""),
            "last_seen": addr_info.get("last_seen_receiving", ""),
            "tags": tags,
            "extracted_identifiers": [],
        }

    def _chain_divisor(self, chain: str) -> float:
        """Return divisor to convert smallest unit to main unit."""
        divisors: dict[str, float] = {
            "bitcoin": 1e8,
            "litecoin": 1e8,
            "bitcoin-cash": 1e8,
            "dogecoin": 1e8,
            "ethereum": 1e18,
            "tron": 1e6,
            "ripple": 1e6,
            "stellar": 1e7,
        }
        return divisors.get(chain, 1e8)
