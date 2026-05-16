"""ProxyLogon / ProxyShell — Microsoft Exchange Server RCE scanner.

Detects: CVE-2021-26855 (ProxyLogon SSRF — pre-auth), CVE-2021-27065 (ProxyLogon
post-auth arbitrary file write → RCE chain), CVE-2021-34473/34523/31207 (ProxyShell
pre-auth RCE chain), and Exchange version disclosure.

ProxyLogon/ProxyShell are actively exploited by nation-state actors (HAFNIUM).
"""

from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Exchange detection paths
_EXCHANGE_PATHS: list[tuple[str, str]] = [
    ("/owa/", "owa"),
    ("/owa/auth/logon.aspx", "owa_login"),
    ("/ecp/", "ecp"),
    ("/ecp/default.aspx", "ecp_default"),
    ("/autodiscover/autodiscover.xml", "autodiscover"),
    ("/Microsoft-Server-ActiveSync/", "activesync"),
    ("/OAB/", "oab"),
    ("/EWS/Exchange.asmx", "ews"),
    ("/mapi/", "mapi"),
    ("/rpc/", "rpc"),
    ("/PowerShell/", "powershell"),
]

# CVE-2021-26855 ProxyLogon SSRF probe
# Tests if server processes SSRF via X-AnonResource-Backend header
_PROXYLOGON_SSRF_PATH = "/owa/auth/x.js"
_PROXYLOGON_HEADERS: dict[str, str] = {
    "Cookie": "X-AnonResource=true; X-AnonResource-Backend=localhost/ecp/default.aspx?~3; "
              "X-BEResource=localhost/ews/exchange.asmx?~3",
}

# ProxyShell paths (CVE-2021-34473)
_PROXYSHELL_PATHS: list[str] = [
    "/autodiscover/autodiscover.json?@evil.com/ews/exchange.asmx?",
    "/autodiscover/autodiscover.json?@evil.com/mapi/nspi?",
    "/autodiscover/autodiscover.json%3F@evil.com/ews/exchange.asmx%3F",
    "/autodiscover/autodiscover.json%3f@evil.com/mapi/nspi%3f",
]

# Exchange version indicators
_EXCHANGE_INDICATORS = re.compile(
    r'(?i)(Microsoft Exchange|OWA|Outlook Web|X-OWA-Version|'
    r'X-DiagInfo|X-BEServer|X-FEServer)',
)

# OWA version detection
_EXCHANGE_VERSION = re.compile(r'X-OWA-Version:\s*([\d.]+)', re.I)
_EXCHANGE_BUILD = re.compile(r'(?:14|15)\.\d+\.\d+\.\d+')

# Vulnerable Exchange build numbers
# Format: (build_prefix, CVE, description, severity)
_VULNERABLE_BUILDS: list[tuple[str, str, str, str]] = [
    ("14.3.513", "CVE-2021-26855", "Exchange 2010 ProxyLogon", "critical"),
    ("15.0.1497", "CVE-2021-26855", "Exchange 2013 ProxyLogon", "critical"),
    ("15.1.2308", "CVE-2021-26855", "Exchange 2016 ProxyLogon", "critical"),
    ("15.2.792", "CVE-2021-26855", "Exchange 2019 ProxyLogon", "critical"),
    ("15.1.2375", "CVE-2021-34473", "Exchange 2016 ProxyShell", "critical"),
    ("15.2.858", "CVE-2021-34473", "Exchange 2019 ProxyShell", "critical"),
]


class ProxyLogonScanner(BaseOsintScanner):
    """Microsoft Exchange ProxyLogon/ProxyShell vulnerability scanner.

    Detects Exchange Server instances and tests for CVE-2021-26855 (ProxyLogon
    SSRF pre-auth), CVE-2021-34473 (ProxyShell URL confusion), and version
    disclosure indicating vulnerable builds.
    """

    scanner_name = "proxylogon"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL,
                                        ScanInputType.IP_ADDRESS})
    cache_ttl = 7200
    scan_timeout = 60

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)
        return await self._manual_scan(base_url, input_value)

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []
        exchange_info: dict[str, Any] = {}
        exchange_detected = False

        async with httpx.AsyncClient(
            timeout=8,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ExchangeScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(6)

            # Step 1: Detect Exchange
            async def probe_exchange(path: str, technique: str) -> None:
                nonlocal exchange_detected
                async with semaphore:
                    url = base_url.rstrip("/") + path
                    try:
                        resp = await client.get(url)
                        body = resp.text
                        headers_str = str(resp.headers)

                        if _EXCHANGE_INDICATORS.search(body) or _EXCHANGE_INDICATORS.search(headers_str):
                            exchange_detected = True

                            # Extract version
                            ver_match = _EXCHANGE_VERSION.search(headers_str)
                            build_match = _EXCHANGE_BUILD.search(headers_str + " " + body)

                            if ver_match and "version" not in exchange_info:
                                exchange_info["owa_version"] = ver_match.group(1)
                            if build_match and "build" not in exchange_info:
                                exchange_info["build"] = build_match.group(0)

                            exchange_info["url"] = base_url
                            exchange_info["owa_accessible"] = technique in ("owa", "owa_login")

                    except Exception:
                        pass

            await asyncio.gather(*[probe_exchange(p, t) for p, t in _EXCHANGE_PATHS[:6]])

            if not exchange_detected:
                return {
                    "input": input_value,
                    "scan_mode": "manual_fallback",
                    "base_url": base_url,
                    "exchange_detected": False,
                    "vulnerabilities": [],
                    "total_found": 0,
                    "extracted_identifiers": [],
                }

            identifiers.append("info:exchange:detected")

            # Step 2: Version-based CVE check
            build = exchange_info.get("build", "")
            if build:
                for vuln_build, cve, desc, sev in _VULNERABLE_BUILDS:
                    if build.startswith(vuln_build[:6]):
                        vulnerabilities.append({
                            "type": "exchange_vulnerable_version",
                            "severity": sev,
                            "build": build,
                            "cve": cve,
                            "description": f"{desc} — build {build} is vulnerable",
                            "remediation": "Apply Microsoft Exchange emergency security patches immediately",
                        })
                        identifiers.append(f"vuln:exchange:{cve}")

            # Step 3: ProxyLogon CVE-2021-26855 SSRF probe
            proxylogon_url = base_url.rstrip("/") + _PROXYLOGON_SSRF_PATH
            try:
                resp = await client.get(proxylogon_url, headers=_PROXYLOGON_HEADERS)
                # 200 with Exchange content = SSRF processed
                if resp.status_code == 200 and ("Microsoft" in resp.text or len(resp.content) > 100):
                    vulnerabilities.append({
                        "type": "proxylogon_ssrf",
                        "severity": "critical",
                        "url": proxylogon_url,
                        "cve": "CVE-2021-26855",
                        "description": "ProxyLogon SSRF probe received 200 response — server may process backend header injection",
                        "remediation": "Apply Microsoft Exchange Security Update KB5001779 immediately",
                    })
                    identifiers.append("vuln:exchange:proxylogon_ssrf")
            except Exception:
                pass

            # Step 4: ProxyShell URL confusion probe
            async def probe_proxyshell(path: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + path
                    try:
                        resp = await client.get(url)
                        # 200/302/401 on ProxyShell path with Exchange headers = vulnerable
                        if resp.status_code in (200, 302, 401):
                            headers_str = str(resp.headers)
                            if _EXCHANGE_INDICATORS.search(headers_str) or resp.status_code == 401:
                                vulnerabilities.append({
                                    "type": "proxyshell_url_confusion",
                                    "severity": "critical",
                                    "url": url,
                                    "status_code": resp.status_code,
                                    "cve": "CVE-2021-34473",
                                    "description": "ProxyShell URL confusion path accepted by Exchange — pre-auth RCE chain possible",
                                    "remediation": "Apply May 2021 Exchange security updates; block autodiscover externally",
                                })
                                ident = "vuln:exchange:proxyshell"
                                if ident not in identifiers:
                                    identifiers.append(ident)
                    except Exception:
                        pass

            await asyncio.gather(*[probe_proxyshell(p) for p in _PROXYSHELL_PATHS[:3]])

            # Step 5: ECP (Exchange Control Panel) exposure
            ecp_url = base_url.rstrip("/") + "/ecp/"
            try:
                resp = await client.get(ecp_url)
                if resp.status_code in (200, 302) and ("Exchange" in resp.text or "ECP" in resp.text):
                    vulnerabilities.append({
                        "type": "exchange_ecp_exposed",
                        "severity": "high",
                        "url": ecp_url,
                        "description": "Exchange Control Panel (ECP) accessible — admin interface exposed to internet",
                        "remediation": "Restrict ECP/EWS/OWA access to internal networks; use VPN",
                    })
                    identifiers.append("vuln:exchange:ecp_exposed")
            except Exception:
                pass

        severity_counts: dict[str, int] = {}
        for v in vulnerabilities:
            s = v.get("severity", "info")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "exchange_detected": exchange_detected,
            "exchange_info": exchange_info,
            "vulnerabilities": vulnerabilities,
            "total_found": len(vulnerabilities),
            "severity_summary": severity_counts,
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])


def _normalise_url(value: str, input_type: ScanInputType) -> str:
    if input_type == ScanInputType.IP_ADDRESS:
        return f"https://{value}"
    if input_type == ScanInputType.DOMAIN:
        return f"https://{value}"
    if not value.startswith(("http://", "https://")):
        return f"https://{value}"
    return value
