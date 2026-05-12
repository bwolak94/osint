"""Compromised IP Checker — verify if an IP address has an abuse history.

Module 50 in the Credential Intelligence domain. Queries AbuseIPDB (requires
optional API key) with fallback to InternetDB for free checks.
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.config import get_settings
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# AbuseIPDB abuse category labels
_CATEGORIES: dict[int, str] = {
    1: "DNS Compromise", 2: "DNS Poisoning", 3: "Fraud Orders",
    4: "DDoS Attack", 5: "FTP Brute Force", 6: "Ping of Death",
    7: "Phishing", 8: "Fraud VoIP", 9: "Open Proxy",
    10: "Web Spam", 11: "Email Spam", 12: "Blog Spam",
    13: "VPN IP", 14: "Port Scan", 15: "Hacking",
    16: "SQL Injection", 17: "Spoofing", 18: "Brute Force",
    19: "Bad Web Bot", 20: "Exploited Host", 21: "Web App Attack",
    22: "SSH Abuse", 23: "IoT Targeted",
}


class CompromisedIPCheckerScanner(BaseOsintScanner):
    """Check an IP address for abuse history using AbuseIPDB.

    With ABUSEIPDB_API_KEY configured, returns confidence score (0-100),
    total abuse reports, and abuse category breakdown. Falls back to
    InternetDB (Shodan free) for basic tag information without a key.
    """

    scanner_name = "compromised_ip"
    supported_input_types = frozenset({ScanInputType.IP_ADDRESS})
    cache_ttl = 3600

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        ip = input_value.strip()
        settings = get_settings()
        api_key = getattr(settings, "abuseipdb_api_key", None)

        if api_key:
            return await self._query_abuseipdb(ip, api_key)
        return await self._query_internetdb_fallback(ip)

    async def _query_abuseipdb(self, ip: str, api_key: str) -> dict[str, Any]:
        """Query AbuseIPDB v2 API."""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.abuseipdb.com/api/v2/check",
                headers={"Key": api_key, "Accept": "application/json"},
                params={"ipAddress": ip, "maxAgeInDays": 90, "verbose": ""},
            )
            if resp.status_code != 200:
                return {"found": False, "ip": ip, "error": f"AbuseIPDB returned {resp.status_code}"}

            data = resp.json().get("data", {})
            score = data.get("abuseConfidenceScore", 0)
            reports = data.get("totalReports", 0)
            categories_raw = data.get("reports", [])

            # Count category frequencies
            cat_freq: dict[str, int] = {}
            for report in categories_raw[:50]:  # Limit processing
                for cat_id in report.get("categories", []):
                    name = _CATEGORIES.get(cat_id, f"Category {cat_id}")
                    cat_freq[name] = cat_freq.get(name, 0) + 1

            top_categories = sorted(cat_freq.items(), key=lambda x: x[1], reverse=True)[:5]

            return {
                "found": score > 0 or reports > 0,
                "ip": ip,
                "abuse_confidence_score": score,
                "total_reports": reports,
                "isp": data.get("isp", ""),
                "country_code": data.get("countryCode", ""),
                "usage_type": data.get("usageType", ""),
                "is_whitelisted": data.get("isWhitelisted", False),
                "is_tor": data.get("isTor", False),
                "top_abuse_categories": [{"category": c, "count": n} for c, n in top_categories],
                "source": "abuseipdb",
            }

    async def _query_internetdb_fallback(self, ip: str) -> dict[str, Any]:
        """Free fallback using InternetDB (Shodan)."""
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                resp = await client.get(f"https://internetdb.shodan.io/{ip}")
                if resp.status_code == 404:
                    return {"found": False, "ip": ip, "source": "internetdb", "note": "No data found"}
                if resp.status_code != 200:
                    return {"found": False, "ip": ip, "error": f"InternetDB returned {resp.status_code}"}

                data = resp.json()
                tags = data.get("tags", [])
                vulns = data.get("vulns", [])

                is_compromised = any(t in tags for t in ["compromised", "malware", "botnet", "tor"])

                return {
                    "found": bool(tags) or bool(vulns),
                    "ip": ip,
                    "tags": tags,
                    "known_vulns": vulns[:10],
                    "ports": data.get("ports", [])[:20],
                    "is_likely_compromised": is_compromised,
                    "source": "internetdb",
                    "note": "Set ABUSEIPDB_API_KEY for full abuse confidence score",
                }
            except Exception as exc:
                return {"found": False, "ip": ip, "error": str(exc)}
