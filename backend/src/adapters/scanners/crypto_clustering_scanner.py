"""Cryptocurrency wallet clustering scanner.

Uses common-input-ownership heuristic and blockchain APIs to:
- Find all transactions for a wallet address
- Identify co-spend clusters (wallets likely owned by same entity)
- Check wallet against known exchange/darknet labels
- Compute transaction volume and risk indicators
- Sources: Blockchair, Blockchain.info, WalletExplorer
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_BTC_RE = re.compile(r'^(bc1|[13])[a-zA-HJ-NP-Z0-9]{25,39}$')
_ETH_RE = re.compile(r'^0x[a-fA-F0-9]{40}$')
_BLOCKCHAIR = "https://api.blockchair.com"
_WALLETEXPLORER = "https://www.walletexplorer.com/api/1/address"


class CryptoClusteringScanner(BaseOsintScanner):
    """Cryptocurrency wallet clustering and risk analysis scanner."""

    scanner_name = "crypto_clustering"
    supported_input_types = frozenset({ScanInputType.USERNAME, ScanInputType.EMAIL,
                                        ScanInputType.DOMAIN})
    cache_ttl = 3600
    scan_timeout = 30

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        return await self._manual_scan(input_value, input_type)

    async def _manual_scan(self, query: str, input_type: ScanInputType) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        identifiers: list[str] = []

        # Detect if query IS a wallet address
        is_btc = bool(_BTC_RE.match(query))
        is_eth = bool(_ETH_RE.match(query))

        if not (is_btc or is_eth):
            return {
                "input": query,
                "scan_mode": "manual_fallback",
                "findings": [],
                "total_found": 0,
                "note": "Input is not a recognized BTC or ETH address",
                "extracted_identifiers": [],
            }

        coin = "bitcoin" if is_btc else "ethereum"

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; CryptoScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(3)

            # 1. Blockchair address stats
            async def blockchair_stats() -> None:
                async with semaphore:
                    try:
                        resp = await client.get(
                            f"{_BLOCKCHAIR}/{coin}/dashboards/address/{query}",
                            timeout=8,
                        )
                        if resp.status_code == 200:
                            import json as _json
                            data = _json.loads(resp.text)
                            addr_data = data.get("data", {}).get(query, {})
                            addr = addr_data.get("address", {})
                            txs = addr_data.get("transactions", [])

                            if addr:
                                received = addr.get("received", 0)
                                sent = addr.get("spent", 0)
                                balance = addr.get("balance", 0)
                                tx_count = addr.get("transaction_count", 0)
                                first_seen = addr.get("first_seen_receiving")
                                last_seen = addr.get("last_seen_receiving")

                                # Risk indicators
                                risk_flags: list[str] = []
                                if received > 10_000_000_000:  # >100 BTC equivalent
                                    risk_flags.append("high_volume")
                                if tx_count > 1000:
                                    risk_flags.append("high_transaction_count")

                                identifiers.append("info:crypto:address_found")
                                findings.append({
                                    "type": "crypto_address_stats",
                                    "severity": "high" if risk_flags else "medium",
                                    "source": "Blockchair",
                                    "address": query,
                                    "coin": coin,
                                    "balance_satoshi": balance,
                                    "total_received": received,
                                    "total_sent": sent,
                                    "transaction_count": tx_count,
                                    "first_seen": first_seen,
                                    "last_seen": last_seen,
                                    "risk_flags": risk_flags,
                                    "recent_tx_count": len(txs[:5]),
                                    "description": f"{coin.upper()} address {query[:16]}...: {tx_count} txs, "
                                                   f"balance={balance}",
                                })
                    except Exception as exc:
                        log.debug("Blockchair stats error", error=str(exc))

            # 2. WalletExplorer label lookup (BTC only)
            async def walletexplorer_label() -> None:
                if not is_btc:
                    return
                async with semaphore:
                    try:
                        resp = await client.get(
                            f"{_WALLETEXPLORER}?address={query}&caller=osint-scanner",
                            timeout=8,
                        )
                        if resp.status_code == 200:
                            import json as _json
                            data = _json.loads(resp.text)
                            wallet_id = data.get("wallet_id")
                            label = data.get("label")
                            if label or wallet_id:
                                identifiers.append("info:crypto:wallet_labeled")
                                is_exchange = any(
                                    kw in (label or "").lower()
                                    for kw in ("binance", "coinbase", "kraken", "huobi",
                                               "bitfinex", "exchange", "mixer", "tumbl")
                                )
                                findings.append({
                                    "type": "crypto_wallet_label",
                                    "severity": "high" if "mixer" in (label or "").lower() else "medium",
                                    "source": "WalletExplorer",
                                    "address": query,
                                    "wallet_id": wallet_id,
                                    "label": label,
                                    "is_exchange": is_exchange,
                                    "description": f"Wallet labeled as '{label}'" + (" (EXCHANGE)" if is_exchange else ""),
                                })
                    except Exception as exc:
                        log.debug("WalletExplorer error", error=str(exc))

            # 3. Blockchain.info co-spend cluster hint (BTC)
            async def cluster_hint() -> None:
                if not is_btc:
                    return
                async with semaphore:
                    try:
                        resp = await client.get(
                            f"https://blockchain.info/rawaddr/{query}?limit=5",
                            timeout=8,
                        )
                        if resp.status_code == 200:
                            import json as _json
                            data = _json.loads(resp.text)
                            txs = data.get("txs", [])
                            # Collect all input addresses from same transactions (co-spend heuristic)
                            co_spend: set[str] = set()
                            for tx in txs[:3]:
                                inputs = tx.get("inputs", [])
                                input_addrs = [
                                    inp.get("prev_out", {}).get("addr")
                                    for inp in inputs
                                    if inp.get("prev_out", {}).get("addr") and
                                    inp.get("prev_out", {}).get("addr") != query
                                ]
                                co_spend.update(input_addrs[:5])
                            if co_spend:
                                identifiers.append("info:crypto:cluster_found")
                                findings.append({
                                    "type": "crypto_co_spend_cluster",
                                    "severity": "medium",
                                    "source": "Blockchain.info",
                                    "address": query,
                                    "cluster_addresses": list(co_spend)[:10],
                                    "cluster_size": len(co_spend),
                                    "description": f"Co-spend cluster: {len(co_spend)} addresses likely controlled by same entity",
                                })
                    except Exception as exc:
                        log.debug("Blockchain.info cluster error", error=str(exc))

            await asyncio.gather(blockchair_stats(), walletexplorer_label(), cluster_hint())

        return {
            "input": query,
            "scan_mode": "manual_fallback",
            "coin": coin,
            "address": query,
            "findings": findings,
            "total_found": len(findings),
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])
