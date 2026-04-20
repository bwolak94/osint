"""Etherscan enhanced scanner — deep Ethereum address analysis with ENS resolution."""

import asyncio
import re
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.config import get_settings
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_ETHERSCAN_BASE = "https://api.etherscan.io/api"
_THEGRAPH_ENS = "https://api.thegraph.com/subgraphs/name/ensdomains/ens"
_ETH_ADDR_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")

# Known contract addresses associated with high-risk activity (heuristic examples)
_MIXER_ADDRS = {
    "0xd90e2f925da726b50c4ed8d0fb90ad053324f31b",  # Tornado Cash router (example)
}


class EtherscanEnhancedScanner(BaseOsintScanner):
    scanner_name = "etherscan_enhanced"
    supported_input_types = frozenset({ScanInputType.DOMAIN})
    cache_ttl = 300

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        # Accept raw ETH address or extract from input
        addr = self._extract_eth_address(input_value)
        if not addr:
            return {
                "input": input_value,
                "found": False,
                "error": "No valid Ethereum address found in input",
                "extracted_identifiers": [],
            }

        settings = get_settings()
        api_key = settings.etherscan_api_key

        params_base: dict[str, str] = {"apikey": api_key} if api_key else {}

        async with httpx.AsyncClient(timeout=20) as client:
            results = await asyncio.gather(
                self._get_balance(client, addr, params_base),
                self._get_tx_list(client, addr, params_base),
                self._get_token_transfers(client, addr, params_base),
                self._get_contract_source(client, addr, params_base),
                self._get_bytecode(client, addr, params_base),
                self._resolve_ens(client, addr),
                return_exceptions=True,
            )

        balance_data = results[0] if not isinstance(results[0], BaseException) else {}
        tx_data = results[1] if not isinstance(results[1], BaseException) else {}
        token_data = results[2] if not isinstance(results[2], BaseException) else {}
        contract_data = results[3] if not isinstance(results[3], BaseException) else {}
        code_data = results[4] if not isinstance(results[4], BaseException) else {}
        ens_name = results[5] if not isinstance(results[5], BaseException) else ""

        eth_balance = balance_data.get("balance_eth", 0.0)
        recent_txs: list[dict[str, Any]] = tx_data.get("transactions", [])
        tx_count: int = tx_data.get("total_count", len(recent_txs))
        token_transfers: list[dict[str, Any]] = token_data.get("transfers", [])
        is_contract: bool = bool(code_data.get("is_contract", False))

        interacted_contracts = list({
            tx.get("to", "").lower()
            for tx in recent_txs
            if tx.get("to") and tx.get("to", "").lower() != addr.lower()
        })

        risk_indicators = self._assess_risk(addr, recent_txs, interacted_contracts)

        return {
            "address": addr,
            "is_contract": is_contract,
            "ens_name": str(ens_name) if ens_name else "",
            "eth_balance": eth_balance,
            "tx_count": tx_count,
            "recent_txs": recent_txs[:20],
            "token_transfers": token_transfers[:20],
            "interacted_contracts": interacted_contracts[:50],
            "risk_indicators": risk_indicators,
            "contract_name": contract_data.get("contract_name", ""),
            "extracted_identifiers": [],
        }

    def _extract_eth_address(self, value: str) -> str:
        value = value.strip()
        if _ETH_ADDR_RE.match(value):
            return value.lower()
        match = re.search(r"0x[0-9a-fA-F]{40}", value)
        return match.group().lower() if match else ""

    async def _get_balance(
        self, client: httpx.AsyncClient, addr: str, base: dict[str, str]
    ) -> dict[str, Any]:
        try:
            resp = await client.get(
                _ETHERSCAN_BASE,
                params={**base, "module": "account", "action": "balance", "address": addr, "tag": "latest"},
            )
            data = resp.json()
            if data.get("status") == "1":
                wei = int(data.get("result", 0))
                return {"balance_eth": wei / 1e18, "balance_wei": wei}
        except Exception as exc:
            log.debug("Etherscan balance failed", addr=addr, error=str(exc))
        return {}

    async def _get_tx_list(
        self, client: httpx.AsyncClient, addr: str, base: dict[str, str]
    ) -> dict[str, Any]:
        try:
            resp = await client.get(
                _ETHERSCAN_BASE,
                params={
                    **base,
                    "module": "account",
                    "action": "txlist",
                    "address": addr,
                    "startblock": "0",
                    "endblock": "latest",
                    "sort": "desc",
                    "offset": "20",
                    "page": "1",
                },
            )
            data = resp.json()
            if data.get("status") == "1":
                txs = data.get("result", [])
                simplified = [
                    {
                        "hash": t.get("hash"),
                        "from": t.get("from"),
                        "to": t.get("to"),
                        "value_eth": int(t.get("value", 0)) / 1e18,
                        "timestamp": t.get("timeStamp"),
                        "gas_used": t.get("gasUsed"),
                    }
                    for t in txs
                ]
                return {"transactions": simplified, "total_count": len(txs)}
        except Exception as exc:
            log.debug("Etherscan txlist failed", addr=addr, error=str(exc))
        return {}

    async def _get_token_transfers(
        self, client: httpx.AsyncClient, addr: str, base: dict[str, str]
    ) -> dict[str, Any]:
        try:
            resp = await client.get(
                _ETHERSCAN_BASE,
                params={
                    **base,
                    "module": "account",
                    "action": "tokentx",
                    "address": addr,
                    "sort": "desc",
                    "offset": "20",
                    "page": "1",
                },
            )
            data = resp.json()
            if data.get("status") == "1":
                transfers = [
                    {
                        "token_name": t.get("tokenName"),
                        "token_symbol": t.get("tokenSymbol"),
                        "from": t.get("from"),
                        "to": t.get("to"),
                        "value": t.get("value"),
                        "timestamp": t.get("timeStamp"),
                    }
                    for t in data.get("result", [])
                ]
                return {"transfers": transfers}
        except Exception as exc:
            log.debug("Etherscan token transfers failed", addr=addr, error=str(exc))
        return {}

    async def _get_contract_source(
        self, client: httpx.AsyncClient, addr: str, base: dict[str, str]
    ) -> dict[str, Any]:
        try:
            resp = await client.get(
                _ETHERSCAN_BASE,
                params={**base, "module": "contract", "action": "getsourcecode", "address": addr},
            )
            data = resp.json()
            if data.get("status") == "1":
                result = data.get("result", [{}])
                if result and result[0].get("ContractName"):
                    return {"contract_name": result[0]["ContractName"], "is_verified": True}
        except Exception as exc:
            log.debug("Etherscan contract source failed", addr=addr, error=str(exc))
        return {}

    async def _get_bytecode(
        self, client: httpx.AsyncClient, addr: str, base: dict[str, str]
    ) -> dict[str, Any]:
        try:
            resp = await client.get(
                _ETHERSCAN_BASE,
                params={**base, "module": "proxy", "action": "eth_getCode", "address": addr, "tag": "latest"},
            )
            data = resp.json()
            code = data.get("result", "0x")
            return {"is_contract": isinstance(code, str) and len(code) > 4}
        except Exception as exc:
            log.debug("Etherscan bytecode failed", addr=addr, error=str(exc))
        return {"is_contract": False}

    async def _resolve_ens(self, client: httpx.AsyncClient, addr: str) -> str:
        query = """
        {
          domains(where: {resolvedAddress: "%s"}) {
            name
          }
        }
        """ % addr.lower()
        try:
            resp = await client.post(_THEGRAPH_ENS, json={"query": query}, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                domains = data.get("data", {}).get("domains", [])
                if domains:
                    return domains[0].get("name", "")
        except Exception as exc:
            log.debug("ENS resolution failed", addr=addr, error=str(exc))
        return ""

    def _assess_risk(
        self, addr: str, recent_txs: list[dict[str, Any]], interacted: list[str]
    ) -> list[str]:
        indicators: list[str] = []
        interacted_lower = {c.lower() for c in interacted}
        for mixer in _MIXER_ADDRS:
            if mixer in interacted_lower:
                indicators.append(f"Interacted with known mixer: {mixer}")
        if len(recent_txs) > 15:
            indicators.append("High transaction frequency")
        return indicators
