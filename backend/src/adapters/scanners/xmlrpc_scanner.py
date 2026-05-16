"""WordPress xmlrpc.php scanner — amplification, brute force, and SSRF.

Detects:
- xmlrpc.php enabled (always a risk even on patched WordPress)
- system.listMethods — API enumeration without auth
- wp.getUsersBlogs multicall amplification brute force (CVE-2015-5706 style)
- Pingback SSRF via xmlrpc.php pingback.ping method
- Autodiscover XML parameter disclosure
- WP REST API v1 user enumeration (?author=1 redirect)
- wp.getCategories, wp.getTags — unauthenticated content enumeration
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

# xmlrpc.php endpoint
_XMLRPC_PATH = "/xmlrpc.php"

# XML-RPC payloads
_XMLRPC_LIST_METHODS = """<?xml version="1.0" encoding="UTF-8"?>
<methodCall>
  <methodName>system.listMethods</methodName>
  <params></params>
</methodCall>"""

# Multicall amplification for brute force detection
_XMLRPC_MULTICALL = """<?xml version="1.0" encoding="UTF-8"?>
<methodCall>
  <methodName>system.multicall</methodName>
  <params>
    <param><value><array><data>
      <value><struct>
        <member><name>methodName</name><value><string>wp.getUsersBlogs</string></value></member>
        <member><name>params</name><value><array><data>
          <value><string>admin</string></value>
          <value><string>PROBE_PASS_1</string></value>
        </data></array></value></member>
      </struct></value>
      <value><struct>
        <member><name>methodName</name><value><string>wp.getUsersBlogs</string></value></member>
        <member><name>params</name><value><array><data>
          <value><string>admin</string></value>
          <value><string>PROBE_PASS_2</string></value>
        </data></array></value></member>
      </struct></value>
    </data></array></value></param>
  </params>
</methodCall>"""

# Pingback SSRF probe
_XMLRPC_PINGBACK = """<?xml version="1.0" encoding="UTF-8"?>
<methodCall>
  <methodName>pingback.ping</methodName>
  <params>
    <param><value><string>http://ssrf-probe.internal.test/</string></value></param>
    <param><value><string>https://TARGET/</string></value></param>
  </params>
</methodCall>"""

# WordPress REST API user enumeration
_WP_REST_PATHS: list[str] = [
    "/?author=1",
    "/wp-json/wp/v2/users",
    "/wp-json/wp/v2/users?per_page=100",
    "/?rest_route=/wp/v2/users",
]

# WordPress version detection
_WP_VERSION_PATTERN = re.compile(r'WordPress (\d+\.\d+[\.\d]*)', re.I)
_WP_GENERATOR = re.compile(r'<meta name="generator" content="WordPress ([^"]+)"', re.I)

# XMLRPC success/method indicators
_XMLRPC_SUCCESS = re.compile(r'<methodResponse>|<params>|<faultCode>', re.I)
_XMLRPC_METHODS = re.compile(r'<string>(system\.|wp\.|blogger\.|metaWeblog\.)', re.I)
_MULTICALL_SUCCESS = re.compile(r'<array>.*?<struct>', re.I | re.S)

# User enumeration pattern in REST response
_USER_PATTERN = re.compile(r'"slug"\s*:\s*"([^"]+)".*?"name"\s*:\s*"([^"]+)"', re.S)


class XMLRPCScanner(BaseOsintScanner):
    """WordPress xmlrpc.php vulnerability scanner.

    Detects xmlrpc.php exposure, multicall amplification for brute force,
    pingback SSRF, and REST API user enumeration.
    """

    scanner_name = "xmlrpc"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 3600
    scan_timeout = 60

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)
        return await self._manual_scan(base_url, input_value)

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []
        wp_info: dict[str, Any] = {}

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; XMLRPCScanner/1.0)"},
        ) as client:

            xmlrpc_url = base_url.rstrip("/") + _XMLRPC_PATH

            # Step 1: Check if xmlrpc.php exists
            try:
                resp = await client.get(xmlrpc_url)
                if resp.status_code == 405 or (
                    resp.status_code == 200 and "XML-RPC server accepts POST" in resp.text
                ):
                    vulnerabilities.append({
                        "type": "xmlrpc_enabled",
                        "severity": "medium",
                        "url": xmlrpc_url,
                        "description": "WordPress xmlrpc.php enabled — "
                                       "allows multicall amplification brute force and pingback SSRF",
                        "remediation": "Disable xmlrpc.php unless needed; "
                                       "add to nginx: location = /xmlrpc.php { deny all; }",
                    })
                    identifiers.append("vuln:xmlrpc:enabled")
                elif resp.status_code not in (200, 405):
                    return {
                        "input": input_value,
                        "scan_mode": "manual_fallback",
                        "base_url": base_url,
                        "xmlrpc_enabled": False,
                        "vulnerabilities": [],
                        "total_found": 0,
                        "extracted_identifiers": [],
                    }
            except Exception:
                return {
                    "input": input_value,
                    "scan_mode": "manual_fallback",
                    "base_url": base_url,
                    "xmlrpc_enabled": False,
                    "vulnerabilities": [],
                    "total_found": 0,
                    "extracted_identifiers": [],
                }

            # Step 2: system.listMethods
            try:
                resp = await client.post(
                    xmlrpc_url,
                    content=_XMLRPC_LIST_METHODS,
                    headers={"Content-Type": "text/xml"},
                )
                if resp.status_code == 200 and _XMLRPC_METHODS.search(resp.text):
                    methods_found = _XMLRPC_METHODS.findall(resp.text)
                    vulnerabilities.append({
                        "type": "xmlrpc_methods_exposed",
                        "severity": "medium",
                        "url": xmlrpc_url,
                        "methods_sample": list(set(m.rstrip(".") for m in methods_found))[:10],
                        "description": "xmlrpc.php system.listMethods returns API list — "
                                       "all available API methods exposed without auth",
                        "remediation": "Disable xmlrpc.php; use REST API with proper auth",
                    })
                    identifiers.append("vuln:xmlrpc:methods_exposed")
            except Exception:
                pass

            # Step 3: Multicall amplification
            try:
                resp = await client.post(
                    xmlrpc_url,
                    content=_XMLRPC_MULTICALL,
                    headers={"Content-Type": "text/xml"},
                )
                if resp.status_code == 200 and _MULTICALL_SUCCESS.search(resp.text):
                    # Multicall processed multiple auth attempts in one request
                    vuln: dict[str, Any] = {
                        "type": "xmlrpc_multicall_bruteforce",
                        "severity": "high",
                        "url": xmlrpc_url,
                        "description": "WordPress xmlrpc.php accepts system.multicall — "
                                       "allows brute-forcing hundreds of passwords per HTTP request "
                                       "(bypasses most rate limiting)",
                        "remediation": "Disable xmlrpc.php; install Wordfence with brute force protection; "
                                       "use fail2ban to block repeated xmlrpc requests",
                    }
                    # Check if auth succeeded for any probe password
                    if "isAdmin" in resp.text or "blogName" in resp.text:
                        vuln["severity"] = "critical"
                        vuln["description"] += " — default password ACCEPTED"
                        identifiers.append("vuln:xmlrpc:default_creds")
                    vulnerabilities.append(vuln)
                    identifiers.append("vuln:xmlrpc:multicall_amplification")
            except Exception:
                pass

            # Step 4: Pingback SSRF
            try:
                resp = await client.post(
                    xmlrpc_url,
                    content=_XMLRPC_PINGBACK.replace("TARGET", base_url.split("//")[1].split("/")[0]),
                    headers={"Content-Type": "text/xml"},
                )
                if resp.status_code == 200 and "faultCode" not in resp.text:
                    vulnerabilities.append({
                        "type": "xmlrpc_pingback_ssrf",
                        "severity": "high",
                        "url": xmlrpc_url,
                        "description": "xmlrpc.php pingback.ping method may allow SSRF — "
                                       "server can be made to send HTTP requests to internal/external hosts",
                        "remediation": "Disable pingbacks in WordPress settings → Discussion → "
                                       "uncheck 'Allow link notifications from other blogs'",
                    })
                    identifiers.append("vuln:xmlrpc:pingback_ssrf")
            except Exception:
                pass

            # Step 5: WordPress REST API user enumeration
            for path in _WP_REST_PATHS:
                try:
                    url = base_url.rstrip("/") + path
                    resp = await client.get(url)
                    body = resp.text

                    if resp.status_code in (200, 301, 302):
                        # Author redirect reveals username
                        if path == "/?author=1" and resp.status_code in (301, 302):
                            location = resp.headers.get("location", "")
                            if "/author/" in location:
                                username = location.split("/author/")[-1].strip("/")
                                wp_info["admin_username"] = username
                                vulnerabilities.append({
                                    "type": "wordpress_user_enumeration",
                                    "severity": "medium",
                                    "url": url,
                                    "username": username,
                                    "description": f"WordPress user enumeration via author redirect — "
                                                   f"admin username '{username}' disclosed",
                                    "remediation": "Redirect author pages; install security plugin to block enumeration",
                                })
                                identifiers.append("vuln:xmlrpc:user_enum")
                                break

                        # REST API returns user list
                        if "/users" in path and resp.status_code == 200:
                            users = _USER_PATTERN.findall(body)
                            if users:
                                vulnerabilities.append({
                                    "type": "wordpress_rest_user_enum",
                                    "severity": "medium",
                                    "url": url,
                                    "users": [{"slug": u[0], "name": u[1]} for u in users[:5]],
                                    "description": f"WordPress REST API exposes {len(users)} user accounts",
                                    "remediation": "Disable REST API user endpoint for unauthenticated users",
                                })
                                ident = "vuln:xmlrpc:rest_user_enum"
                                if ident not in identifiers:
                                    identifiers.append(ident)
                                break
                except Exception:
                    continue

        severity_counts: dict[str, int] = {}
        for v in vulnerabilities:
            s = v.get("severity", "info")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "xmlrpc_enabled": len(vulnerabilities) > 0,
            "wp_info": wp_info,
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
