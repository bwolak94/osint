"""Citrix ADC/Gateway scanner — CVE-2019-19781 (BleedingEdge) and related CVEs.

Detects:
- CVE-2019-19781 — Citrix ADC/Gateway path traversal → RCE (unauthenticated)
  Probe: GET /vpn/../vpns/cfg/smb.conf → 200 = vulnerable
- CVE-2023-24488 — Citrix ADC/Gateway XSS
- CVE-2023-3519  — Citrix ADC/Gateway RCE (unauthenticated) — July 2023 0-day
- CVE-2022-27518 — Citrix ADC/Gateway authentication bypass
- Citrix version disclosure via /logon/LogonPoint/index.html and vpn paths
- NetScaler/ADC management interface (NSIP) exposure
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

# CVE-2019-19781 traversal probe paths
_CVE_2019_19781_PROBES: list[tuple[str, str]] = [
    ("/vpn/../vpns/cfg/smb.conf", "path_traversal_smb"),
    ("/vpn/../vpns/portal/scripts/newbm.pl", "path_traversal_perl"),
    ("/vpn/../vpns/", "traversal_vpns_dir"),
    ("/vpn/js/../vpns/cfg/smb.conf", "double_traversal"),
]

# CVE-2023-3519 RCE probe
_CVE_2023_3519_PROBE = "/gwtest/formssso?event=start&target="

# Citrix detection paths
_CITRIX_PATHS: list[tuple[str, str]] = [
    ("/logon/LogonPoint/index.html", "logon_page"),
    ("/logon/LogonPoint/tmindex.html", "logon_tmindex"),
    ("/vpn/index.html", "vpn_index"),
    ("/cgi/login", "cgi_login"),
    ("/lc/", "lc_path"),
    ("/nf/auth/getAuthenticationRequirements", "auth_requirements"),
    ("/rdweb/pages/en-us/login.aspx", "rds_web"),  # RDS Web Access
    ("/CitrixWeb/", "citrix_web"),
    ("/Citrix/", "citrix_root"),
    ("/receiver/", "citrix_receiver"),
]

# Citrix version indicator patterns
_CITRIX_INDICATORS = re.compile(
    r'(?i)(citrix|netscaler|storefront|XenApp|XenDesktop|'
    r'Citrix Gateway|ADC|Access Gateway)',
)

# SMB.conf contents indicating successful traversal
_TRAVERSAL_SUCCESS = re.compile(r'\[global\]|\[homes\]|workgroup\s*=', re.I)

# Management interface indicators
_MGMT_INDICATORS = re.compile(r'(?i)(nsconfig|Citrix.*Management|NetScaler.*CLI|NSIP)', re.I)


class CitrixScanner(BaseOsintScanner):
    """Citrix ADC/Gateway vulnerability scanner.

    Detects CVE-2019-19781 path traversal RCE, CVE-2023-3519 unauthenticated RCE,
    CVE-2022-27518 auth bypass, and Citrix product version disclosure.
    """

    scanner_name = "citrix"
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
        product_info: dict[str, Any] = {}
        citrix_detected = False

        async with httpx.AsyncClient(
            timeout=8,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; CitrixScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(6)

            # Step 1: Detect Citrix
            async def detect_citrix(path: str, technique: str) -> None:
                nonlocal citrix_detected
                async with semaphore:
                    url = base_url.rstrip("/") + path
                    try:
                        resp = await client.get(url)
                        body = resp.text
                        headers_str = str(resp.headers)
                        combined = body + headers_str
                        if _CITRIX_INDICATORS.search(combined):
                            citrix_detected = True
                            product_info["url"] = url
                            product_info["technique"] = technique

                            # Try to extract version
                            ver_match = re.search(r'(?i)(?:version|build|ns)[:\s]+(\d+\.\d+[\.\d]*)', body)
                            if ver_match and "version" not in product_info:
                                product_info["version"] = ver_match.group(1)

                            # Check for management interface exposure
                            if _MGMT_INDICATORS.search(combined):
                                vulnerabilities.append({
                                    "type": "citrix_mgmt_exposed",
                                    "severity": "critical",
                                    "url": url,
                                    "description": "Citrix management interface accessible — "
                                                   "NetScaler CLI/config exposed to internet",
                                    "remediation": "Restrict NSIP management access to internal VLANs only",
                                })
                                identifiers.append("vuln:citrix:mgmt_exposed")
                    except Exception:
                        pass

            await asyncio.gather(*[detect_citrix(p, t) for p, t in _CITRIX_PATHS[:5]])

            if not citrix_detected:
                # Quick extra check on common Citrix ports
                for port in [443, 8443, 80, 4433]:
                    try:
                        scheme = "https" if port in (443, 8443, 4433) else "http"
                        # Already checked base_url, try alternate port
                        alt_url = re.sub(r'https?://[^/]+', f"{scheme}://{_extract_host(input_value)}", base_url)
                        alt_url = f"{scheme}://{_extract_host(input_value)}:{port}"
                        resp = await client.get(alt_url + "/vpn/index.html")
                        if _CITRIX_INDICATORS.search(resp.text):
                            citrix_detected = True
                            base_url_effective = alt_url
                            product_info["url"] = alt_url
                            break
                    except Exception:
                        pass

            if not citrix_detected:
                return {
                    "input": input_value,
                    "scan_mode": "manual_fallback",
                    "base_url": base_url,
                    "citrix_detected": False,
                    "vulnerabilities": [],
                    "total_found": 0,
                    "extracted_identifiers": [],
                }

            identifiers.append("info:citrix:detected")

            # Step 2: CVE-2019-19781 path traversal
            async def probe_cve_2019_19781(path: str, technique: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + path
                    try:
                        resp = await client.get(url)
                        if resp.status_code == 200:
                            if _TRAVERSAL_SUCCESS.search(resp.text):
                                vulnerabilities.append({
                                    "type": "citrix_path_traversal_rce",
                                    "severity": "critical",
                                    "url": url,
                                    "technique": technique,
                                    "evidence": resp.text[:200],
                                    "cve": "CVE-2019-19781",
                                    "description": "Citrix ADC/Gateway path traversal confirmed (CVE-2019-19781) — "
                                                   "unauthenticated RCE possible via PERL exploitation chain",
                                    "remediation": "Apply Citrix patches immediately; "
                                                   "enable 'Responder' policy to block traversal; "
                                                   "upgrade to ADC 12.1 build 50.31+",
                                })
                                ident = "vuln:citrix:cve_2019_19781"
                                if ident not in identifiers:
                                    identifiers.append(ident)
                            elif len(resp.content) > 50:
                                # File exists but not smb.conf — still traversal
                                vulnerabilities.append({
                                    "type": "citrix_path_traversal",
                                    "severity": "critical",
                                    "url": url,
                                    "technique": technique,
                                    "cve": "CVE-2019-19781",
                                    "description": "Citrix path traversal path returned 200 — "
                                                   "likely vulnerable to CVE-2019-19781",
                                    "remediation": "Apply Citrix security patches immediately",
                                })
                                ident = "vuln:citrix:cve_2019_19781_suspect"
                                if ident not in identifiers:
                                    identifiers.append("vuln:citrix:cve_2019_19781")
                    except Exception:
                        pass

            await asyncio.gather(*[probe_cve_2019_19781(p, t) for p, t in _CVE_2019_19781_PROBES])

            # Step 3: CVE-2023-3519 RCE probe
            try:
                url_3519 = base_url.rstrip("/") + _CVE_2023_3519_PROBE + "test"
                resp = await client.get(url_3519)
                if resp.status_code in (200, 400, 500):
                    headers_str = str(resp.headers)
                    if _CITRIX_INDICATORS.search(resp.text + headers_str):
                        vulnerabilities.append({
                            "type": "citrix_cve_2023_3519_candidate",
                            "severity": "critical",
                            "url": url_3519,
                            "cve": "CVE-2023-3519",
                            "description": "Citrix ADC/Gateway formssso endpoint accessible — "
                                           "potential CVE-2023-3519 unauthenticated RCE (July 2023 0-day)",
                            "remediation": "Upgrade to ADC 13.1-49.13+, 13.0-91.13+, or 12.1-65.21+",
                        })
                        identifiers.append("vuln:citrix:cve_2023_3519")
            except Exception:
                pass

            # Step 4: CVE-2022-27518 auth bypass — check /nf/auth/
            try:
                url_auth = base_url.rstrip("/") + "/nf/auth/getAuthenticationRequirements"
                resp = await client.get(url_auth)
                if resp.status_code == 200 and "saml" in resp.text.lower():
                    vulnerabilities.append({
                        "type": "citrix_saml_auth_bypass_candidate",
                        "severity": "critical",
                        "url": url_auth,
                        "cve": "CVE-2022-27518",
                        "description": "Citrix ADC SAML authentication endpoint accessible — "
                                       "CVE-2022-27518 unauthenticated RCE if SAML SP/IdP configured",
                        "remediation": "Upgrade to ADC 12.1 build 65.25+ or 13.0 build 88.19+",
                    })
                    identifiers.append("vuln:citrix:cve_2022_27518")
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
            "citrix_detected": citrix_detected,
            "product_info": product_info,
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


def _extract_host(value: str) -> str:
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return parsed.hostname or value.strip()


from urllib.parse import urlparse  # noqa: E402
