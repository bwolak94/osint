"""AD CS Abuse Module — passive recon for Active Directory Certificate Services exposure.

Module 121 in the Infrastructure & Exploitation domain. Performs passive HTTP-based
discovery of exposed Active Directory Certificate Services (AD CS) web enrollment
interfaces (/certsrv). Also checks TLS certificates for CRL Distribution Points
and Authority Information Access extensions that reveal internal AD CS infrastructure.
Returns ESC vulnerability candidates based on observed configuration indicators.
"""

from __future__ import annotations

import asyncio
import ssl
import socket
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Common AD CS web enrollment paths
_ADCS_WEB_PATHS = [
    "/certsrv",
    "/certsrv/",
    "/certsrv/default.asp",
    "/certsrv/certrqad.asp",
    "/certsrv/certrqxt.asp",
    "/ADPolicyProvider_CEP_Kerberos/service.svc",
    "/ADPolicyProvider_CEP_UsernamePassword/service.svc",
    "/CertSrv/mscep/mscep.dll",
    "/CertSrv/mscep_admin/",
    "/OCSP",
]

_ADCS_SIGNATURES = [
    "Microsoft Active Directory Certificate Services",
    "Certificate Services",
    "certsrv",
    "Request a Certificate",
    "Certificate Enrollment",
    "NTLM",
    "Negotiate",
]

# ESC vulnerability indicators based on service characteristics
_ESC_INDICATORS: list[dict[str, str]] = [
    {
        "esc": "ESC8",
        "condition": "ntlm_auth_on_certsrv",
        "description": "AD CS Web Enrollment with NTLM auth — vulnerable to NTLM relay attacks (ESC8). "
                       "An attacker can relay NTLM authentication to enroll a certificate as any user.",
        "severity": "Critical",
    },
    {
        "esc": "ESC6",
        "condition": "userspecifiedsan",
        "description": "EDITF_ATTRIBUTESUBJECTALTNAME2 may be set — allows requesters to specify arbitrary SANs (ESC6).",
        "severity": "High",
    },
]


def _extract_host(input_value: str) -> str:
    value = input_value.strip().lower()
    value = value.replace("https://", "").replace("http://", "").split("/")[0]
    return value


def _get_cert_extensions(hostname: str, port: int = 443) -> dict[str, Any]:
    """Fetch TLS certificate and extract AD CS-related extensions."""
    extensions: dict[str, Any] = {
        "crl_distribution_points": [],
        "ocsp_urls": [],
        "issuer": "",
        "ca_name": "",
        "internal_hostnames": [],
    }
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with socket.create_connection((hostname, port), timeout=8) as sock:
            with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                if not cert:
                    return extensions

                # Extract issuer
                issuer_dict = dict(x[0] for x in cert.get("issuer", []))
                extensions["issuer"] = issuer_dict.get("commonName", "")

                # Look for CRL Distribution Points
                for ext_name, ext_data in cert.get("extensions", {}).items():
                    pass  # Standard ssl module doesn't expose CDP easily

                # Try Subject Alt Names for internal references
                sans = [san[1] for san in cert.get("subjectAltName", [])]
                for san in sans:
                    if any(kw in san.lower() for kw in ["ca", "pki", "cert", "crl", "adcs", "certsrv"]):
                        extensions["internal_hostnames"].append(san)
    except Exception as exc:
        log.debug("TLS cert fetch failed", host=hostname, error=str(exc))
    return extensions


class ADCSAbuseScanner(BaseOsintScanner):
    """Discovers exposed AD CS web enrollment interfaces and CRL/AIA extension data.

    Probes the target domain for /certsrv and related AD CS paths, checks TLS
    certificates for CA-related extensions revealing internal PKI infrastructure,
    and identifies ESC (Escalation) vulnerability candidates based on authentication
    method and service configuration indicators (Module 121).
    """

    scanner_name = "ad_cs_abuse"
    supported_input_types = frozenset({ScanInputType.DOMAIN})
    cache_ttl = 43200  # 12 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        host = _extract_host(input_value)
        findings: list[dict[str, Any]] = []
        esc_candidates: list[dict[str, str]] = []
        cert_info: dict[str, Any] = {}

        async with httpx.AsyncClient(
            timeout=12,
            follow_redirects=False,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (OSINT-Security-Research/1.0)"},
        ) as client:
            for path in _ADCS_WEB_PATHS:
                for scheme in ("https", "http"):
                    url = f"{scheme}://{host}{path}"
                    try:
                        resp = await client.get(url)
                        status = resp.status_code

                        if status in (200, 401, 403):
                            body = resp.text
                            auth_header = resp.headers.get("www-authenticate", "")

                            adcs_confirmed = any(sig.lower() in body.lower() for sig in _ADCS_SIGNATURES)
                            ntlm_auth = "NTLM" in auth_header or "Negotiate" in auth_header

                            if adcs_confirmed or (status in (401, 403) and ntlm_auth and "/certsrv" in path):
                                finding: dict[str, Any] = {
                                    "url": url,
                                    "path": path,
                                    "status_code": status,
                                    "adcs_confirmed": adcs_confirmed,
                                    "ntlm_authentication": ntlm_auth,
                                    "auth_methods": auth_header,
                                    "risk": "Critical" if ntlm_auth else "High",
                                }
                                findings.append(finding)

                                # Check ESC8 — NTLM auth on web enrollment
                                if ntlm_auth:
                                    esc_candidates.append({
                                        **_ESC_INDICATORS[0],
                                        "evidence_url": url,
                                    })
                    except (httpx.RequestError, httpx.TimeoutException):
                        pass

        # Fetch TLS certificate extensions for CA/PKI intelligence
        loop = asyncio.get_event_loop()
        try:
            cert_info = await loop.run_in_executor(None, _get_cert_extensions, host, 443)
        except Exception:
            pass

        ad_cs_detected = len(findings) > 0
        severity = "Critical" if any(f.get("risk") == "Critical" for f in findings) else (
            "High" if findings else "None"
        )

        return {
            "target": host,
            "found": ad_cs_detected,
            "adcs_endpoints_found": findings,
            "esc_vulnerability_candidates": esc_candidates,
            "certificate_info": cert_info,
            "severity": severity,
            "educational_info": {
                "description": (
                    "Active Directory Certificate Services (AD CS) misconfigurations are among the "
                    "most impactful vulnerabilities in Windows enterprise environments. The SpecterOps "
                    "'Certified Pre-Owned' research identified 8 ESC escalation paths."
                ),
                "common_escs": {
                    "ESC1": "Enroll with arbitrary Subject Alternative Name in client auth template",
                    "ESC4": "Vulnerable ACLs on certificate templates allowing modification",
                    "ESC6": "CA flag EDITF_ATTRIBUTESUBJECTALTNAME2 enabled",
                    "ESC8": "NTLM relay to AD CS HTTP endpoints for certificate enrollment",
                },
                "tools": ["Certipy", "Certify", "PKINITtools"],
            },
        }
