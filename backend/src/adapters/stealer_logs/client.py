"""Stealer log intelligence client.

Queries Hudson Rock Cavalier API for infostealer breach data.
Requires HUDSON_ROCK_API_KEY environment variable.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class Infection:
    source: str  # hudson_rock / osintleak
    stealer_family: str | None = None
    date_compromised: str | None = None
    computer_name: str | None = None
    operating_system: str | None = None
    ip: str | None = None
    country: str | None = None
    credentials_count: int = 0
    cookies_count: int = 0
    autofill_count: int = 0
    has_crypto_wallet: bool = False
    risk_level: str = "unknown"  # low/medium/high/critical
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class StealerLogResult:
    query: str
    query_type: str
    total_infections: int = 0
    infections: list[dict[str, Any]] = field(default_factory=list)
    sources_checked: list[str] = field(default_factory=list)


class StealerLogClient:
    """Query Hudson Rock Cavalier API for infostealer log data."""

    _HR_BASE = "https://cavalier.hudsonrock.com/api/json/v2"
    _TIMEOUT = 20.0

    def __init__(self) -> None:
        self._hr_key = os.getenv("HUDSON_ROCK_API_KEY", "")

    async def query(self, target: str, query_type: str) -> StealerLogResult:
        """Query stealer logs for a target (email, domain, or IP)."""
        result = StealerLogResult(query=target, query_type=query_type)
        sources_checked: list[str] = []

        if self._hr_key:
            try:
                infections = await self._query_hudson_rock(target, query_type)
                result.infections.extend(infections)
                sources_checked.append("Hudson Rock Cavalier")
            except Exception as exc:
                result.infections.append({
                    "source": "hudson_rock",
                    "error": str(exc),
                    "stealer_family": None,
                    "date_compromised": None,
                    "computer_name": None,
                    "operating_system": None,
                    "ip": None,
                    "country": None,
                    "credentials_count": 0,
                    "cookies_count": 0,
                    "autofill_count": 0,
                    "has_crypto_wallet": False,
                    "risk_level": "unknown",
                    "raw": {},
                })
        else:
            result.infections.append({
                "source": "configuration",
                "error": "HUDSON_ROCK_API_KEY not configured. Set this environment variable to enable stealer log queries.",
                "stealer_family": None,
                "date_compromised": None,
                "computer_name": None,
                "operating_system": None,
                "ip": None,
                "country": None,
                "credentials_count": 0,
                "cookies_count": 0,
                "autofill_count": 0,
                "has_crypto_wallet": False,
                "risk_level": "unknown",
                "raw": {},
            })
            sources_checked.append("Not configured")

        result.sources_checked = sources_checked
        result.total_infections = len([i for i in result.infections if "error" not in i])
        return result

    async def _query_hudson_rock(self, target: str, query_type: str) -> list[dict[str, Any]]:
        """Query Hudson Rock Cavalier API."""
        endpoints: dict[str, str] = {
            "email": f"{self._HR_BASE}/osint-tools/search-by-email",
            "domain": f"{self._HR_BASE}/osint-tools/search-by-domain",
            "ip": f"{self._HR_BASE}/osint-tools/search-by-ip",
        }
        endpoint = endpoints.get(query_type)
        if not endpoint:
            return []

        params: dict[str, str] = {
            "email" if query_type == "email" else
            "domain" if query_type == "domain" else
            "ip": target,
        }

        async with httpx.AsyncClient(timeout=self._TIMEOUT) as client:
            resp = await client.get(
                endpoint,
                params=params,
                headers={"api-key": self._hr_key, "User-Agent": "OSINT-Platform/1.0"},
            )
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            data = resp.json()

        infections: list[dict[str, Any]] = []
        for item in data.get("stealers", []):
            creds = item.get("credentials", [])
            cookies = item.get("cookies", [])
            autofill = item.get("autofill", [])
            has_crypto = any(
                "crypto" in str(c).lower() or "wallet" in str(c).lower()
                for c in creds + cookies
            )

            cred_count = len(creds)
            cookie_count = len(cookies)
            risk = "critical" if cred_count > 50 or cookie_count > 100 else \
                   "high" if cred_count > 10 or cookie_count > 20 else \
                   "medium" if cred_count > 0 or cookie_count > 0 else "low"

            infections.append({
                "source": "hudson_rock",
                "stealer_family": item.get("stealer_type"),
                "date_compromised": item.get("date_uploaded"),
                "computer_name": item.get("computer_name"),
                "operating_system": item.get("operating_system"),
                "ip": item.get("ip"),
                "country": item.get("country"),
                "credentials_count": cred_count,
                "cookies_count": cookie_count,
                "autofill_count": len(autofill),
                "has_crypto_wallet": has_crypto,
                "risk_level": risk,
                "raw": {k: v for k, v in item.items() if k not in ("credentials", "cookies", "autofill")},
            })

        return infections
