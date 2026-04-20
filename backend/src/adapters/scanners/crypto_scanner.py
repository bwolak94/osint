"""Crypto address scanner — traces blockchain transactions for BTC and ETH addresses."""

import re
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.adapters.scanners.exceptions import RateLimitError
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_REQUEST_TIMEOUT = 20

# Address detection patterns
_BTC_RE = re.compile(r"^(1[a-km-zA-HJ-NP-Z1-9]{25,34}|3[a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[a-z0-9]{6,87})$")
_ETH_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")


def _detect_address_type(address: str) -> str | None:
    """Return 'BTC', 'ETH', or None if the address is unrecognised."""
    if _BTC_RE.match(address):
        return "BTC"
    if _ETH_RE.match(address):
        return "ETH"
    return None


class CryptoAddressScanner(BaseOsintScanner):
    """Queries public blockchain APIs to trace transaction history and linked
    addresses for Bitcoin and Ethereum wallets.

    Configuration note:
        etherscan_api_key (str): Set via ETHERSCAN_API_KEY env var for higher
            rate limits. An empty string falls back to the public (rate-limited)
            Etherscan endpoint.
    """

    scanner_name = "crypto_tracer"
    # URL input type is used as a proxy since there is no dedicated CRYPTO input type.
    # Callers should pass the raw crypto address string as `input_value`.
    supported_input_types = frozenset({ScanInputType.URL})
    cache_ttl = 3600  # 1 hour — blockchain data changes constantly

    def __init__(self, etherscan_api_key: str = "", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._etherscan_api_key = etherscan_api_key

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        address = input_value.strip()
        address_type = _detect_address_type(address)

        if address_type is None:
            return {
                "address": address,
                "found": False,
                "error": (
                    "Unrecognised address format. "
                    "Expected BTC (starts with 1/3/bc1) or ETH (starts with 0x)."
                ),
                "extracted_identifiers": [],
            }

        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            if address_type == "BTC":
                return await self._scan_btc(client, address)
            return await self._scan_eth(client, address)

    # ------------------------------------------------------------------ BTC
    async def _scan_btc(self, client: httpx.AsyncClient, address: str) -> dict[str, Any]:
        """Query Blockchair for Bitcoin address information."""
        url = f"https://api.blockchair.com/bitcoin/dashboards/address/{address}"
        try:
            resp = await client.get(url, params={"limit": 50})

            if resp.status_code == 429:
                raise RateLimitError("Blockchair rate limited")
            if resp.status_code != 200:
                log.warning("Blockchair unexpected response", status=resp.status_code, address=address)
                return self._not_found(address, "BTC")

            payload = resp.json()
            addr_data: dict[str, Any] = (
                payload.get("data", {}).get(address, {}).get("address", {})
            )
            txs: list[dict[str, Any]] = (
                payload.get("data", {}).get(address, {}).get("transactions", [])
            )

            if not addr_data:
                return self._not_found(address, "BTC")

            total_received: int = addr_data.get("received", 0)
            total_sent: int = addr_data.get("spent", 0)
            tx_count: int = addr_data.get("transaction_count", 0)
            first_seen: str = addr_data.get("first_seen_receiving", "") or ""
            last_seen: str = addr_data.get("last_seen_sending", "") or ""

            # Extract linked addresses from the transaction list (counterparties)
            linked: list[str] = list(
                {
                    tx.get("hash", "")
                    for tx in txs
                    if tx.get("hash") and tx.get("hash") != address
                }
            )[:20]

            identifiers = [f"domain:btc-{addr}" for addr in linked]  # best proxy

            return {
                "address": address,
                "address_type": "BTC",
                "found": True,
                "transaction_count": tx_count,
                "total_received_satoshi": total_received,
                "total_sent_satoshi": total_sent,
                "total_received_btc": round(total_received / 1e8, 8),
                "total_sent_btc": round(total_sent / 1e8, 8),
                "first_seen": first_seen,
                "last_seen": last_seen,
                "linked_tx_hashes": linked,
                "extracted_identifiers": identifiers,
            }

        except RateLimitError:
            raise
        except Exception as exc:
            log.warning("Blockchair BTC query failed", address=address, error=str(exc))
            return self._not_found(address, "BTC", error=str(exc))

    # ------------------------------------------------------------------ ETH
    async def _scan_eth(self, client: httpx.AsyncClient, address: str) -> dict[str, Any]:
        """Query Etherscan for Ethereum address transaction history."""
        params: dict[str, str] = {
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": "0",
            "endblock": "99999999",
            "page": "1",
            "offset": "50",
            "sort": "desc",
        }
        if self._etherscan_api_key:
            params["apikey"] = self._etherscan_api_key

        url = "https://api.etherscan.io/api"
        try:
            resp = await client.get(url, params=params)

            if resp.status_code == 429:
                raise RateLimitError("Etherscan rate limited")
            if resp.status_code != 200:
                log.warning("Etherscan unexpected response", status=resp.status_code, address=address)
                return self._not_found(address, "ETH")

            payload = resp.json()
            if payload.get("status") != "1":
                message = payload.get("message", "")
                if "No transactions found" in message:
                    return {
                        **self._not_found(address, "ETH"),
                        "found": True,
                        "transaction_count": 0,
                    }
                return self._not_found(address, "ETH", error=message)

            txs: list[dict[str, Any]] = payload.get("result", [])

            linked: list[str] = []
            total_received: int = 0
            total_sent: int = 0
            first_seen: str = ""
            last_seen: str = ""

            for tx in txs:
                value_wei = int(tx.get("value", 0))
                if tx.get("to", "").lower() == address.lower():
                    total_received += value_wei
                else:
                    total_sent += value_wei

                counterparty = (
                    tx.get("from", "") if tx.get("to", "").lower() == address.lower()
                    else tx.get("to", "")
                )
                if counterparty and counterparty.lower() != address.lower():
                    if counterparty not in linked:
                        linked.append(counterparty)

            if txs:
                first_seen = txs[-1].get("timeStamp", "")
                last_seen = txs[0].get("timeStamp", "")

            identifiers = [f"domain:eth-{addr[:10]}" for addr in linked[:10]]

            return {
                "address": address,
                "address_type": "ETH",
                "found": True,
                "transaction_count": len(txs),
                "total_received_wei": total_received,
                "total_sent_wei": total_sent,
                "total_received_eth": round(total_received / 1e18, 8),
                "total_sent_eth": round(total_sent / 1e18, 8),
                "first_seen_timestamp": first_seen,
                "last_seen_timestamp": last_seen,
                "linked_addresses": linked[:20],
                "extracted_identifiers": identifiers,
            }

        except RateLimitError:
            raise
        except Exception as exc:
            log.warning("Etherscan query failed", address=address, error=str(exc))
            return self._not_found(address, "ETH", error=str(exc))

    @staticmethod
    def _not_found(address: str, address_type: str, error: str | None = None) -> dict[str, Any]:
        result: dict[str, Any] = {
            "address": address,
            "address_type": address_type,
            "found": False,
            "extracted_identifiers": [],
        }
        if error:
            result["error"] = error
        return result
