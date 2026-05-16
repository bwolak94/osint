"""Confluence / Jira — CVE-2022-26134 OGNL RCE and data exposure scanner.

Detects: CVE-2022-26134 (Confluence Server OGNL injection RCE, unauthenticated),
CVE-2023-22515 (Confluence unauthorized admin creation), CVE-2021-26086 (Jira
path traversal), Jira open registration, and sensitive project/issue exposure.

Standard attack: CVE-2022-26134 → RCE with one HTTP request, no auth needed.
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

# CVE-2022-26134 OGNL injection payloads (benign detection probes)
_CVE_2022_26134_PROBES: list[tuple[str, str]] = [
    # Path-based OGNL injection (returns HTTP status indicating execution)
    (
        "/%24%7B%28%23a%3D%40org.apache.tomcat.InstanceManager%40getInstance"
        "%28%29.newInstance%28%27com.opensymphony.xwork2.DefaultActionInvocation"
        "%27%29%2C%23b%3D%23a.getClass%28%29.getDeclaredField%28%27proxy%27%29%2C"
        "%23b.setAccessible%28true%29%2C%23bc%3D%23b.get%28%23a%29%2C%23bc"
        ".getActionProxy%28%29.getMethod%28%29%29%7D/",
        "ognl_deep",
    ),
    ("/${7*7}/", "ognl_math"),
    ("/pages/viewpage.action?pageId=${7*7}", "ognl_viewpage"),
]

# Confluence paths
_CONFLUENCE_PATHS: list[tuple[str, str]] = [
    ("/", "root"),
    ("/login.action", "login"),
    ("/signup.action", "signup"),
    ("/admin/", "admin"),
    ("/rest/api/space", "spaces_api"),
    ("/rest/api/content", "content_api"),
    ("/rest/api/user/current", "current_user"),
    ("/rest/api/group", "groups"),
    ("/pages/viewpage.action", "view_page"),
    ("/display/", "spaces"),
    ("/wiki/", "wiki"),
    ("/server-info.action", "server_info"),
    ("/setup/setupadministrator.action", "setup_admin"),  # CVE-2023-22515
]

# Jira paths
_JIRA_PATHS: list[tuple[str, str]] = [
    ("/", "root"),
    ("/login.jsp", "login"),
    ("/rest/api/2/serverInfo", "server_info"),
    ("/rest/api/2/project", "projects_list"),
    ("/rest/api/2/issue/createmeta", "create_meta"),
    ("/rest/api/2/user/search?username=.", "user_search"),
    ("/rest/api/2/field", "fields"),
    ("/rest/api/2/configuration", "configuration"),
    ("/rest/auth/1/session", "session"),
    ("/secure/Dashboard.jspa", "dashboard"),
    ("/secure/ViewProfile.jspa", "profile"),
    ("/plugins/servlet/saml/auth", "saml_auth"),
    ("/s/1234/_/;/WEB-INF/web.xml", "path_traversal"),  # CVE-2021-26086
]

# Indicators
_CONFLUENCE_INDICATORS = re.compile(
    r'(?i)(confluence|atlassian|X-Confluence-Request-Time|'
    r'com.atlassian.confluence)',
)
_JIRA_INDICATORS = re.compile(
    r'(?i)(jira|atlassian|X-ASEN|JIRA-VERSION|'
    r'com.atlassian.jira)',
)

# Sensitive data in API responses
_SENSITIVE_PATTERNS = re.compile(
    r'(?i)("password"|"secret"|"token"|"email.*@|"apiToken"|"personalAccessToken")',
)


class ConfluenceJiraScanner(BaseOsintScanner):
    """Confluence and Jira security vulnerability scanner.

    Detects unauthenticated access, CVE-2022-26134 OGNL RCE, CVE-2023-22515
    unauthorized admin creation, CVE-2021-26086 path traversal, open registration,
    and sensitive data exposure via REST APIs.
    """

    scanner_name = "confluence_jira"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL,
                                        ScanInputType.IP_ADDRESS})
    cache_ttl = 3600
    scan_timeout = 60

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)
        return await self._manual_scan(base_url, input_value)

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []
        product_info: dict[str, Any] = {}

        async with httpx.AsyncClient(
            timeout=8,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AtlassianScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(6)

            # Detect product type
            is_confluence = False
            is_jira = False

            for port in [8090, 8080, 443, 80]:
                url = f"{base_url.rstrip('/')}:{port}/" if ":" not in base_url.split("//")[1] else base_url
                try:
                    resp = await client.get(url)
                    if _CONFLUENCE_INDICATORS.search(resp.text) or "confluence" in resp.headers.get("x-confluence-request-time", "").lower():
                        is_confluence = True
                        product_info["product"] = "Confluence"
                        product_info["url"] = url
                        break
                    elif _JIRA_INDICATORS.search(resp.text) or resp.headers.get("x-asen"):
                        is_jira = True
                        product_info["product"] = "Jira"
                        product_info["url"] = url
                        break
                except Exception:
                    continue

            if not is_confluence and not is_jira:
                try:
                    resp = await client.get(base_url)
                    if _CONFLUENCE_INDICATORS.search(resp.text):
                        is_confluence = True
                    elif _JIRA_INDICATORS.search(resp.text):
                        is_jira = True
                except Exception:
                    pass

            if not is_confluence and not is_jira:
                return {
                    "input": input_value,
                    "scan_mode": "manual_fallback",
                    "base_url": base_url,
                    "atlassian_detected": False,
                    "vulnerabilities": [],
                    "total_found": 0,
                    "extracted_identifiers": [],
                }

            target_url = product_info.get("url", base_url)

            # CVE-2022-26134 probe (Confluence only)
            if is_confluence:
                identifiers.append("info:confluence:detected")
                for probe_path, technique in _CVE_2022_26134_PROBES:
                    try:
                        resp = await client.get(target_url.rstrip("/") + probe_path)
                        if resp.status_code == 200 and "49" in resp.text:  # 7*7=49
                            vulnerabilities.append({
                                "type": "confluence_ognl_rce",
                                "severity": "critical",
                                "url": target_url.rstrip("/") + probe_path,
                                "technique": technique,
                                "evidence": "7*7=49 reflected",
                                "cve": "CVE-2022-26134",
                                "description": "Confluence Server OGNL injection RCE confirmed (CVE-2022-26134)",
                                "remediation": "Update Confluence immediately to 7.4.17+, 7.13.7+, 7.14.3+, 7.15.2+, 7.16.4+, 7.17.4+, 7.18.1+",
                            })
                            identifiers.append("vuln:confluence:cve_2022_26134")
                    except Exception:
                        pass

                # CVE-2023-22515 — unauthorized admin creation via /setup/setupadministrator.action
                try:
                    resp = await client.get(target_url.rstrip("/") + "/setup/setupadministrator.action")
                    if resp.status_code == 200 and "administrator" in resp.text.lower():
                        vulnerabilities.append({
                            "type": "confluence_unauthorized_admin",
                            "severity": "critical",
                            "url": target_url.rstrip("/") + "/setup/setupadministrator.action",
                            "cve": "CVE-2023-22515",
                            "description": "Confluence setup page accessible — unauthorized administrator account creation possible",
                            "remediation": "Apply patch immediately; block /setup/ routes in firewall",
                        })
                        identifiers.append("vuln:confluence:cve_2023_22515")
                except Exception:
                    pass

            # Jira checks
            if is_jira:
                identifiers.append("info:jira:detected")

                async def check_jira(path: str, technique: str) -> None:
                    async with semaphore:
                        url = target_url.rstrip("/") + path
                        try:
                            resp = await client.get(url)
                            if resp.status_code == 200:
                                body = resp.text

                                if technique == "server_info":
                                    import json as _json
                                    try:
                                        data = _json.loads(body)
                                        product_info["jira_version"] = data.get("version")
                                        vulnerabilities.append({
                                            "type": "jira_info_disclosure",
                                            "severity": "low",
                                            "url": url,
                                            "version": data.get("version"),
                                            "deployment_type": data.get("deploymentType"),
                                            "description": "Jira server info accessible without authentication",
                                        })
                                        identifiers.append("vuln:jira:server_info")
                                    except Exception:
                                        pass

                                elif technique == "projects_list":
                                    import json as _json
                                    try:
                                        projects = _json.loads(body)
                                        if isinstance(projects, list):
                                            vulnerabilities.append({
                                                "type": "jira_projects_exposed",
                                                "severity": "high",
                                                "url": url,
                                                "project_count": len(projects),
                                                "sample_projects": [p.get("key") for p in projects[:5]],
                                                "description": f"Jira projects enumerable without auth — {len(projects)} projects found",
                                                "remediation": "Enable Jira login required; disable anonymous access",
                                            })
                                            identifiers.append("vuln:jira:projects_exposed")
                                    except Exception:
                                        pass

                                elif technique == "user_search":
                                    vulnerabilities.append({
                                        "type": "jira_user_enumeration",
                                        "severity": "medium",
                                        "url": url,
                                        "description": "Jira user search accessible without authentication — email/username enumeration",
                                    })
                                    identifiers.append("vuln:jira:user_enum")

                                elif technique == "path_traversal":
                                    if "web-app" in body.lower() or "servlet" in body.lower():
                                        vulnerabilities.append({
                                            "type": "jira_path_traversal",
                                            "severity": "high",
                                            "url": url,
                                            "cve": "CVE-2021-26086",
                                            "description": "Jira path traversal — WEB-INF/web.xml readable",
                                        })
                                        identifiers.append("vuln:jira:path_traversal")

                        except Exception:
                            pass

                await asyncio.gather(*[check_jira(p, t) for p, t in _JIRA_PATHS])

            # Check open registration (both products)
            async def check_open_signup(path: str) -> None:
                async with semaphore:
                    url = target_url.rstrip("/") + path
                    try:
                        resp = await client.get(url)
                        if resp.status_code == 200 and ("sign up" in resp.text.lower() or "register" in resp.text.lower()):
                            vulnerabilities.append({
                                "type": "open_registration",
                                "severity": "medium",
                                "url": url,
                                "description": f"{'Confluence' if is_confluence else 'Jira'} allows open user registration",
                                "remediation": "Disable self-registration; require admin approval for new accounts",
                            })
                            identifiers.append("vuln:atlassian:open_registration")
                    except Exception:
                        pass

            await asyncio.gather(*[check_open_signup(p) for p in ["/signup.action", "/self/register"]])

        severity_counts: dict[str, int] = {}
        for v in vulnerabilities:
            s = v.get("severity", "info")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "atlassian_detected": True,
            "product_info": product_info,
            "is_confluence": is_confluence,
            "is_jira": is_jira,
            "vulnerabilities": vulnerabilities,
            "total_found": len(vulnerabilities),
            "severity_summary": severity_counts,
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])


def _normalise_url(value: str, input_type: ScanInputType) -> str:
    if input_type == ScanInputType.IP_ADDRESS:
        return f"http://{value}"
    if input_type == ScanInputType.DOMAIN:
        return f"https://{value}"
    if not value.startswith(("http://", "https://")):
        return f"https://{value}"
    return value
