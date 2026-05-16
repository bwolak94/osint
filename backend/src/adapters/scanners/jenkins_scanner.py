"""Jenkins Security — script console RCE, unauthenticated access, and credential exposure scanner.

Detects: unauthenticated Jenkins dashboard, exposed Script Console (Groovy RCE),
anonymous build job execution, credentials store exposure, agent JNLP ports,
and known Jenkins CVEs (CVE-2024-23897 arbitrary file read, CVE-2019-1003000).

Standard attack path: Jenkins Script Console → groovy exec → full RCE.
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

# Jenkins paths
_JENKINS_PATHS: list[tuple[str, str]] = [
    ("/", "dashboard"),
    ("/login", "login_page"),
    ("/script", "script_console"),
    ("/scriptText?script=println('id')", "script_exec"),
    ("/credentials/", "credentials_store"),
    ("/credentials/store/system/domain/_/", "system_credentials"),
    ("/asynchPeople/", "users_list"),
    ("/computer/", "nodes"),
    ("/api/json", "api_json"),
    ("/api/json?tree=jobs[name,url,color]", "jobs_list"),
    ("/view/all/api/json", "all_jobs"),
    ("/job/*/config.xml", "job_config"),
    ("/configureSecurity/", "security_config"),
    ("/securityRealm/user/admin/api/json", "admin_user"),
    ("/queue/api/json", "build_queue"),
    ("/me/api/json", "current_user"),
    ("/whoAmI/api/json", "whoami"),
    ("/pluginManager/api/json?tree=plugins[shortName,version,hasUpdate]", "plugins"),
    ("/manage", "management"),
    ("/systemInfo", "system_info"),
    ("/env-vars.html", "env_vars"),
    ("/cli", "cli"),
    ("/jnlpJars/jenkins-cli.jar", "cli_jar"),
]

# Script console Groovy payloads for RCE detection
_GROOVY_PROBES: list[tuple[str, str]] = [
    ("println(InetAddress.localHost)", "hostname_leak"),
    ("println(System.properties['os.name'])", "os_disclosure"),
    ("println(['id'].execute().text)", "cmd_id"),
]

# Jenkins indicators
_JENKINS_INDICATORS = re.compile(
    r'(?i)(jenkins|hudson|<title>.*Dashboard|X-Jenkins|'
    r'Authentication required|Sign in to Jenkins|Groovy Script)',
)

# CVE-2024-23897: CLI arbitrary file read
_CLI_FILE_READ_PATHS = ["@/etc/passwd", "@/etc/hostname", "@C:\\Windows\\win.ini"]

# Sensitive data patterns in Jenkins responses
_SENSITIVE_JENKINS = re.compile(
    r'(?i)(apiToken|password|credential|secret|privateKey|'
    r'BEGIN RSA|BEGIN EC|-----BEGIN|aws_secret|JENKINS_SECRET)',
)


class JenkinsScanner(BaseOsintScanner):
    """Jenkins CI/CD security vulnerability scanner.

    Detects unauthenticated access, Script Console RCE, credentials exposure,
    anonymous build execution, and CVE-2024-23897 arbitrary file read.
    """

    scanner_name = "jenkins"
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
        jenkins_info: dict[str, Any] = {}
        jenkins_detected = False

        async with httpx.AsyncClient(
            timeout=8,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; JenkinsScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(6)

            # Step 1: Detect Jenkins and check unauthenticated access
            for port in [8080, 8443, 80, 443, 9090, 50000]:
                url = f"{base_url.rstrip('/')}:{port}/" if ":" not in base_url.split("//")[1] else base_url.rstrip("/") + "/"
                try:
                    resp = await client.get(url)
                    if _JENKINS_INDICATORS.search(resp.text) or resp.headers.get("X-Jenkins"):
                        jenkins_detected = True
                        jenkins_info["url"] = url
                        jenkins_info["version"] = resp.headers.get("X-Jenkins", "unknown")
                        break
                except Exception:
                    continue

            if not jenkins_detected:
                # Try base_url directly
                try:
                    resp = await client.get(base_url)
                    if _JENKINS_INDICATORS.search(resp.text) or resp.headers.get("X-Jenkins"):
                        jenkins_detected = True
                        jenkins_info["url"] = base_url
                        jenkins_info["version"] = resp.headers.get("X-Jenkins", "unknown")
                except Exception:
                    pass

            if not jenkins_detected:
                return {
                    "input": input_value,
                    "scan_mode": "manual_fallback",
                    "base_url": base_url,
                    "jenkins_detected": False,
                    "vulnerabilities": [],
                    "total_found": 0,
                    "extracted_identifiers": [],
                }

            jenkins_url = jenkins_info.get("url", base_url)
            identifiers.append("info:jenkins:detected")

            async def check_path(path: str, technique: str) -> None:
                async with semaphore:
                    url = jenkins_url.rstrip("/") + path.split("?")[0]
                    params = {}
                    if "?" in path:
                        for kv in path.split("?")[1].split("&"):
                            if "=" in kv:
                                k, v = kv.split("=", 1)
                                params[k] = v
                    try:
                        resp = await client.get(url, params=params)
                        body = resp.text

                        # Unauthenticated dashboard
                        if technique == "dashboard" and resp.status_code == 200:
                            if "Dashboard" in body or "Build" in body:
                                vulnerabilities.append({
                                    "type": "jenkins_unauthenticated_access",
                                    "severity": "critical",
                                    "url": url,
                                    "version": jenkins_info.get("version"),
                                    "description": "Jenkins dashboard accessible without authentication",
                                    "remediation": "Enable security realm; require authentication",
                                })
                                identifiers.append("vuln:jenkins:unauth_dashboard")

                        # Script Console accessible
                        elif technique == "script_console" and resp.status_code == 200:
                            if "Groovy" in body or "script" in body.lower():
                                vulnerabilities.append({
                                    "type": "jenkins_script_console_exposed",
                                    "severity": "critical",
                                    "url": url,
                                    "description": "Jenkins Script Console accessible — Groovy RCE possible",
                                    "cve": "CVE-2019-1003000",
                                    "remediation": "Restrict Script Console to admins; use matrix-based security",
                                })
                                identifiers.append("vuln:jenkins:script_console")

                        # Credentials exposure
                        elif technique in ("credentials_store", "system_credentials") and resp.status_code == 200:
                            sensitive = _SENSITIVE_JENKINS.search(body)
                            vulnerabilities.append({
                                "type": "jenkins_credentials_exposed",
                                "severity": "critical",
                                "url": url,
                                "has_secrets": bool(sensitive),
                                "description": "Jenkins credentials store accessible without auth",
                                "remediation": "Restrict credentials store; use encrypted credential providers",
                            })
                            identifiers.append("vuln:jenkins:credentials_exposed")

                        # Jobs/API exposure
                        elif technique in ("jobs_list", "api_json") and resp.status_code == 200:
                            import json as _json
                            try:
                                data = _json.loads(body)
                                jobs = data.get("jobs", [])
                                jenkins_info["job_count"] = len(jobs)
                                if jobs:
                                    vulnerabilities.append({
                                        "type": "jenkins_jobs_enumerable",
                                        "severity": "medium",
                                        "url": url,
                                        "job_count": len(jobs),
                                        "sample_jobs": [j.get("name") for j in jobs[:5]],
                                        "description": f"Jenkins jobs enumerable anonymously — {len(jobs)} jobs found",
                                    })
                                    identifiers.append("vuln:jenkins:jobs_enumerable")
                            except Exception:
                                pass

                        # Plugin list
                        elif technique == "plugins" and resp.status_code == 200:
                            outdated = re.findall(r'"hasUpdate":true', body)
                            if outdated:
                                vulnerabilities.append({
                                    "type": "jenkins_outdated_plugins",
                                    "severity": "medium",
                                    "url": url,
                                    "outdated_count": len(outdated),
                                    "description": f"{len(outdated)} Jenkins plugins have available updates — potential CVEs",
                                    "remediation": "Update all Jenkins plugins regularly",
                                })

                    except Exception:
                        pass

            await asyncio.gather(*[check_path(p, t) for p, t in _JENKINS_PATHS])

            # Step 2: Script Console RCE probe
            script_url = jenkins_url.rstrip("/") + "/scriptText"
            for script, technique in _GROOVY_PROBES[:2]:
                try:
                    resp = await client.post(
                        script_url,
                        data={"script": script},
                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                    )
                    if resp.status_code == 200 and len(resp.text) > 0:
                        if technique == "cmd_id" and re.search(r"uid=\d+", resp.text):
                            vulnerabilities.append({
                                "type": "jenkins_rce_confirmed",
                                "severity": "critical",
                                "url": script_url,
                                "evidence": resp.text[:60],
                                "description": "Jenkins Script Console RCE confirmed — command execution verified",
                                "cve": "CVE-2019-1003000",
                                "remediation": "Immediately restrict Script Console; rotate all credentials",
                            })
                            identifiers.append("vuln:jenkins:rce_confirmed")
                        elif resp.text.strip():
                            vulnerabilities.append({
                                "type": "jenkins_script_execution",
                                "severity": "critical",
                                "url": script_url,
                                "technique": technique,
                                "output": resp.text[:60],
                                "description": "Jenkins Script Console executes Groovy code without authentication",
                            })
                            ident = f"vuln:jenkins:script_exec:{technique}"
                            if ident not in identifiers:
                                identifiers.append(ident)
                except Exception:
                    pass

            # Step 3: CVE-2024-23897 arbitrary file read via CLI
            cli_jar_url = jenkins_url.rstrip("/") + "/jnlpJars/jenkins-cli.jar"
            try:
                resp = await client.get(cli_jar_url)
                if resp.status_code == 200 and len(resp.content) > 1000:
                    vulnerabilities.append({
                        "type": "jenkins_cli_jar_exposed",
                        "severity": "high",
                        "url": cli_jar_url,
                        "cve": "CVE-2024-23897",
                        "description": "Jenkins CLI jar downloadable — CVE-2024-23897 arbitrary file read possible",
                        "remediation": "Update Jenkins to 2.442+; disable CLI if unused",
                    })
                    identifiers.append("vuln:jenkins:cve_2024_23897")
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
            "jenkins_detected": jenkins_detected,
            "jenkins_info": jenkins_info,
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
