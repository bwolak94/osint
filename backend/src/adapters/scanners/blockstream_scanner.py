"""Blockstream.info scanner — Bitcoin address analysis and co-spend clustering."""

import re
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_BASE_URL = "https://blockstream.info/api"

# Legacy (P2PKH/P2SH) and bech32 (P2WPKH/P2WSH) address patterns
_BTC_LEGACY_RE = re.compile(r"^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$")
_BTC_BECH32_RE = re.compile(r"^bc1[a-z0-9]{6,87}$", re.IGNORECASE)

# Small lookup of well-known BTC addresses (exchange hot wallets etc.)
_KNOWN_ENTITIES: dict[str, str] = {
    "1P5ZEDWTKTFGxQjZphgWPQUpe554WKDfHQ": "Binance",
    "34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo": "Binance Cold Wallet",
    "bc1qgdjqv0av3q56jvd82tkdjpy7gdp9ut8tlqmgrpmv24sq90ecnvqqjwvw97": "Bitfinex",
    "1FeexV6bAHb8ybZjqQMjJrcCrHGW9sb6uF": "Mt.Gox (inactive)",
    "3Cbq7aT1tY8kMxWLbitaG7yT6bPbKChq64": "Huobi",
    "bc1qazcm763858nkj2dj986etajv6wquslv8uxwczt": "Kraken",
}


def _is_btc_address(value: str) -> bool:
    return bool(_BTC_LEGACY_RE.match(value)) or bool(_BTC_BECH32_RE.match(value))


class BlockstreamScanner(BaseOsintScanner):
    scanner_name = "blockstream"
    supported_input_types = frozenset({ScanInputType.DOMAIN})
    cache_ttl = 300

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        if not _is_btc_address(input_value):
            return {
                "input": input_value,
                "found": False,
                "error": "Input does not appear to be a valid Bitcoin address",
                "extracted_identifiers": [],
            }
        async with httpx.AsyncClient(timeout=20) as client:
            return await self._analyse_address(client, input_value)

    async def _analyse_address(self, client: httpx.AsyncClient, address: str) -> dict[str, Any]:
        # Step 1: address stats
        stats = await self._get_address_stats(client, address)
        if not stats:
            return {
                "input": address,
                "found": False,
                "error": "Address not found on Blockstream API",
                "extracted_identifiers": [],
            }

        # Step 2: recent transactions
        txs = await self._get_transactions(client, address)

        # Step 3: co-spend clustering and related addresses
        related_addresses = await self._find_related_addresses(client, txs, address)

        # Step 4: known entity check
        is_known = _KNOWN_ENTITIES.get(address)
        risk_indicators = self._assess_risk(stats, is_known)

        chain_stats = stats.get("chain_stats", {})
        mempool_stats = stats.get("mempool_stats", {})
        funded_txo_sum = chain_stats.get("funded_txo_sum", 0) + mempool_stats.get("funded_txo_sum", 0)
        spent_txo_sum = chain_stats.get("spent_txo_sum", 0) + mempool_stats.get("spent_txo_sum", 0)
        balance_sat = funded_txo_sum - spent_txo_sum
        tx_count = chain_stats.get("tx_count", 0) + mempool_stats.get("tx_count", 0)

        recent_txs: list[dict[str, Any]] = [
            {
                "txid": tx.get("txid", ""),
                "fee": tx.get("fee", 0),
                "confirmed": tx.get("status", {}).get("confirmed", False),
                "block_height": tx.get("status", {}).get("block_height"),
                "vin_count": len(tx.get("vin", [])),
                "vout_count": len(tx.get("vout", [])),
            }
            for tx in txs[:10]
        ]

        return {
            "input": address,
            "found": True,
            "address": address,
            "balance_btc": balance_sat / 1e8,
            "total_received_btc": funded_txo_sum / 1e8,
            "total_sent_btc": spent_txo_sum / 1e8,
            "tx_count": tx_count,
            "recent_txs": recent_txs,
            "related_addresses": related_addresses,
            "is_known_entity": is_known,
            "risk_indicators": risk_indicators,
            "extracted_identifiers": [],
        }

    async def _get_address_stats(self, client: httpx.AsyncClient, address: str) -> dict[str, Any]:
        try:
            resp = await client.get(f"{_BASE_URL}/address/{address}")
            if resp.status_code != 200:
                return {}
            return resp.json()
        except Exception as exc:
            log.warning("Blockstream address stats failed", address=address, error=str(exc))
            return {}

    async def _get_transactions(
        self, client: httpx.AsyncClient, address: str
    ) -> list[dict[str, Any]]:
        try:
            resp = await client.get(f"{_BASE_URL}/address/{address}/txs")
            if resp.status_code != 200:
                return []
            return resp.json()
        except Exception as exc:
            log.warning("Blockstream txs fetch failed", address=address, error=str(exc))
            return []

    async def _find_related_addresses(
        self,
        client: httpx.AsyncClient,
        txs: list[dict[str, Any]],
        own_address: str,
    ) -> list[str]:
        """Co-spend heuristic: addresses appearing together as inputs share a wallet."""
        related: set[str] = set()
        for tx in txs[:5]:
            vin = tx.get("vin", [])
            input_addresses = [
                prevout.get("scriptpubkey_address", "")
                for v in vin
                for prevout in [v.get("prevout", {})]
                if prevout.get("scriptpubkey_address") and prevout["scriptpubkey_address"] != own_address
            ]
            if len(vin) > 1:
                # Multiple inputs — co-spend cluster
                related.update(input_addresses)
        return list(related)[:20]

    def _assess_risk(self, stats: dict[str, Any], is_known: str | None) -> list[str]:
        indicators: list[str] = []
        chain_stats = stats.get("chain_stats", {})
        tx_count = chain_stats.get("tx_count", 0)
        if tx_count > 1000:
            indicators.append("high_transaction_volume")
        if is_known:
            indicators.append(f"known_entity:{is_known}")
        return indicators
