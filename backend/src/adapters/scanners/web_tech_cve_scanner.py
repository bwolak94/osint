"""Web Tech CVE — server technology fingerprint to CVE mapping scanner.

Fingerprints web server headers, X-Powered-By, error pages, and response
patterns to identify specific software versions, then cross-references them
against a curated list of high-severity CVEs. Covers Apache, nginx, IIS,
PHP, Django, Rails, Drupal, Joomla, Magento, and 20+ more frameworks.

Supplements whatweb with direct CVE-severity mapping and exploit availability.
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

# (tech_name, version_pattern, cve, severity, description, has_metasploit)
_TECH_CVE_DB: list[tuple[str, re.Pattern[str], str, str, str, bool]] = [
    # Apache
    ("Apache httpd", re.compile(r"Apache/2\.4\.(4[0-9]|[0-3][0-9])\b"), "CVE-2021-41773", "critical", "Apache 2.4.49 path traversal RCE", True),
    ("Apache httpd", re.compile(r"Apache/2\.4\.5[01]\b"), "CVE-2021-42013", "critical", "Apache 2.4.50 path traversal bypass", True),
    ("Apache httpd", re.compile(r"Apache/2\.[02]\.\d"), "CVE-2017-7679", "critical", "Apache 2.x mod_mime buffer overflow", False),
    # nginx
    ("nginx", re.compile(r"nginx/1\.1[0-6]\.\d"), "CVE-2019-9511", "high", "nginx HTTP/2 DoS", False),
    ("nginx", re.compile(r"nginx/1\.[0-9]\.\d"), "CVE-2013-2028", "critical", "nginx stack overflow RCE", True),
    # PHP
    ("PHP", re.compile(r"PHP/[45]\.\d"), "CVE-2019-11043", "critical", "PHP-FPM nginx path RCE (PHP < 7.3.11)", True),
    ("PHP", re.compile(r"PHP/7\.[01]\.\d"), "CVE-2019-11043", "critical", "PHP-FPM path underscore newline RCE", True),
    ("PHP", re.compile(r"PHP/5\.[0-5]\.\d"), "CVE-2012-1823", "critical", "PHP CGI argument injection RCE", True),
    # IIS
    ("IIS", re.compile(r"IIS/[56789]\.\d"), "CVE-2017-7269", "critical", "IIS 6.0 WebDAV buffer overflow RCE", True),
    ("IIS", re.compile(r"IIS/10\.0"), "CVE-2022-21907", "critical", "IIS HTTP protocol stack RCE", False),
    # WordPress
    ("WordPress", re.compile(r"WordPress/[1-5]\.\d"), "CVE-2022-21661", "critical", "WordPress SQL injection < 5.8.3", False),
    ("WordPress", re.compile(r"WordPress/[1-4]\.\d"), "CVE-2019-8943", "high", "WordPress path traversal", False),
    # Drupal
    ("Drupal", re.compile(r"Drupal [78]\.\d"), "CVE-2018-7600", "critical", "Drupalgeddon2 RCE (SA-CORE-2018-002)", True),
    ("Drupal", re.compile(r"Drupal [678]\.\d"), "CVE-2018-7602", "critical", "Drupalgeddon3 RCE", True),
    ("Drupal", re.compile(r"Drupal [67]\.\d"), "CVE-2014-3704", "critical", "Drupalgeddon SQL injection", True),
    # Joomla
    ("Joomla", re.compile(r"Joomla! [123]\.\d"), "CVE-2023-23752", "high", "Joomla 4.x unauthorized API access", False),
    ("Joomla", re.compile(r"Joomla! 1\.[56]\.\d"), "CVE-2015-8562", "critical", "Joomla PHP object injection RCE", True),
    # Magento
    ("Magento", re.compile(r"Magento/1\.\d"), "CVE-2019-8144", "critical", "Magento 2.3 stored XSS RCE chain", True),
    ("Magento", re.compile(r"Magento/2\.[0-3]\.\d"), "CVE-2022-24086", "critical", "Magento pre-auth RCE via template injection", True),
    # Ruby on Rails
    ("Rails", re.compile(r"Rails [45]\.\d"), "CVE-2019-5418", "critical", "Rails path traversal via file format", True),
    ("Rails", re.compile(r"Rails [234]\.\d"), "CVE-2013-0156", "critical", "Rails XML YAML deserialization RCE", True),
    # Django
    ("Django", re.compile(r"Django/[12]\.\d"), "CVE-2021-35042", "critical", "Django SQL injection via queryset.order_by()", False),
    # Tomcat
    ("Tomcat", re.compile(r"Apache Tomcat/[678]\.\d"), "CVE-2017-12617", "critical", "Tomcat PUT JSP upload RCE", True),
    ("Tomcat", re.compile(r"Apache Tomcat/9\.[0-3]\d"), "CVE-2020-1938", "critical", "GhostCat AJP file read/include RCE", True),
    ("Tomcat", re.compile(r"Apache Tomcat/10\.[01]\.\d"), "CVE-2022-42252", "high", "Tomcat request smuggling", False),
    # Struts
    ("Struts", re.compile(r"Struts [12]\.\d"), "CVE-2017-5638", "critical", "Apache Struts2 OGNL injection RCE (Equifax)", True),
    ("Struts", re.compile(r"Struts 2\.[0-3]\.\d"), "CVE-2018-11776", "critical", "Struts2 namespace OGNL RCE", True),
    # Spring
    ("Spring", re.compile(r"Spring Framework [45]\.\d"), "CVE-2022-22965", "critical", "Spring4Shell ClassLoader RCE", True),
    # Node.js / Express
    ("Express", re.compile(r"Express/[23]\.\d"), "CVE-2014-6394", "high", "Express.js open redirect/path traversal", False),
    # WebLogic
    ("WebLogic", re.compile(r"WebLogic Server (1[0-3]|[0-9])\.\d"), "CVE-2020-14882", "critical", "WebLogic unauth RCE via console bypass", True),
    # Jenkins
    ("Jenkins", re.compile(r"Jenkins/(1\.\d|2\.[0-9]\d)\b"), "CVE-2019-1003000", "critical", "Jenkins script sandbox bypass RCE", True),
    # Elasticsearch
    ("Elasticsearch", re.compile(r"Elasticsearch[/ ](1\.|2\.|5\.[0-5])"), "CVE-2015-1427", "critical", "Elasticsearch Groovy sandbox escape RCE", True),
]

# Headers to inspect for version info
_VERSION_HEADERS: list[str] = [
    "Server", "X-Powered-By", "X-Generator", "X-Drupal-Cache",
    "X-WordPress", "X-Joomla-Version", "X-AspNet-Version",
    "X-AspNetMvc-Version",
]

# Error page patterns revealing framework/version
_ERROR_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Apache", re.compile(r"Apache/(\d+\.\d+\.\d+)", re.I)),
    ("PHP", re.compile(r"PHP/(\d+\.\d+\.\d+)", re.I)),
    ("nginx", re.compile(r"nginx/(\d+\.\d+\.\d+)", re.I)),
    ("IIS", re.compile(r"IIS/(\d+\.\d+)", re.I)),
    ("Tomcat", re.compile(r"Apache Tomcat/(\d+\.\d+\.\d+)", re.I)),
    ("Rails", re.compile(r"Rails (\d+\.\d+\.\d+)", re.I)),
    ("Django", re.compile(r"Django/(\d+\.\d+\.\d+)", re.I)),
    ("WordPress", re.compile(r"WordPress/(\d+\.\d+(?:\.\d+)?)", re.I)),
    ("Drupal", re.compile(r"Drupal (\d+\.\d+(?:\.\d+)?)", re.I)),
    ("Joomla", re.compile(r"Joomla! (\d+\.\d+(?:\.\d+)?)", re.I)),
    ("Magento", re.compile(r"Magento/(\d+\.\d+\.\d+)", re.I)),
    ("Jenkins", re.compile(r"Jenkins(?:ver|/) ?(\d+\.\d+(?:\.\d+)?)", re.I)),
    ("Elasticsearch", re.compile(r'"version"\s*:\s*\{\s*"number"\s*:\s*"(\d+\.\d+\.\d+)"')),
    ("WebLogic", re.compile(r"WebLogic Server (\d+\.\d+\.\d+\.\d+)", re.I)),
]

# Probe paths for specific tech detection
_TECH_PROBES: list[tuple[str, str, str]] = [
    # (path, expected_indicator, tech_name)
    ("/wp-login.php", "WordPress", "WordPress"),
    ("/wp-includes/", "WordPress", "WordPress"),
    ("/administrator/", "Joomla", "Joomla"),
    ("/?q=user", "Drupal", "Drupal"),
    ("/misc/drupal.js", "Drupal.settings", "Drupal"),
    ("/skin/frontend/", "Magento", "Magento"),
    ("/magento/", "Magento", "Magento"),
    ("/actuator/health", "status", "Spring Boot"),
    ("/jenkins/", "Jenkins", "Jenkins"),
    ("/_nodes", "elasticsearch", "Elasticsearch"),
    ("/solr/", "Solr", "Solr"),
    ("/struts/", "Struts", "Struts"),
]


class WebTechCVEScanner(BaseOsintScanner):
    """Web technology fingerprinting and CVE-mapping scanner.

    Inspects HTTP response headers, error pages, and known tech-specific
    paths to identify framework/server versions, then cross-references
    against 30+ critical CVEs with Metasploit module availability.
    """

    scanner_name = "web_tech_cve"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 7200
    scan_timeout = 90

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)
        return await self._manual_scan(base_url, input_value)

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []
        tech_detected: dict[str, str] = {}
        all_headers_text = ""
        all_body_text = ""

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; WebTechCVEScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(6)

            # Step 1: Baseline fingerprinting
            try:
                resp = await client.get(base_url)
                all_headers_text = " ".join(f"{k}: {v}" for k, v in resp.headers.items())
                all_body_text = resp.text[:10000]

                # Extract version from headers
                for header in _VERSION_HEADERS:
                    val = resp.headers.get(header, "")
                    if val:
                        for tech, pattern in _ERROR_PATTERNS:
                            m = pattern.search(val)
                            if m:
                                tech_detected[tech] = m.group(1)

                # Extract from body
                for tech, pattern in _ERROR_PATTERNS:
                    m = pattern.search(all_body_text)
                    if m and tech not in tech_detected:
                        tech_detected[tech] = m.group(1)

            except Exception as exc:
                log.debug("WebTechCVE baseline failed", url=base_url, error=str(exc))

            # Step 2: Tech-specific probes
            async def probe_tech(path: str, indicator: str, tech_name: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + path
                    try:
                        resp = await client.get(url)
                        body = resp.text
                        if resp.status_code in (200, 301, 302) and indicator.lower() in body.lower():
                            if tech_name not in tech_detected:
                                # Extract version if present
                                for t, pattern in _ERROR_PATTERNS:
                                    if t.lower() == tech_name.lower():
                                        m = pattern.search(body)
                                        if m:
                                            tech_detected[tech_name] = m.group(1)
                                            break
                                else:
                                    tech_detected[tech_name] = "unknown"
                    except Exception:
                        pass

            await asyncio.gather(*[probe_tech(p, ind, t) for p, ind, t in _TECH_PROBES])

            # Step 3: CVE matching
            full_fingerprint = all_headers_text + " " + all_body_text
            for tech_name, version_regex, cve, severity, description, has_msf in _TECH_CVE_DB:
                match = version_regex.search(full_fingerprint)
                if match:
                    vuln: dict[str, Any] = {
                        "type": "vulnerable_tech_version",
                        "severity": severity,
                        "technology": tech_name,
                        "version_evidence": match.group(0)[:60],
                        "cve": cve,
                        "description": description,
                        "metasploit_available": has_msf,
                        "remediation": f"Update {tech_name} to the latest patched version",
                    }
                    vulnerabilities.append(vuln)
                    ident = f"vuln:tech:{cve}"
                    if ident not in identifiers:
                        identifiers.append(ident)

            # Also check against detected versions
            for tech, version in tech_detected.items():
                for tech_name, version_regex, cve, severity, description, has_msf in _TECH_CVE_DB:
                    if tech.lower() in tech_name.lower() or tech_name.lower() in tech.lower():
                        test_str = f"{tech_name}/{version}"
                        if version_regex.search(test_str):
                            ident = f"vuln:tech:{cve}"
                            if ident not in identifiers:
                                vulnerabilities.append({
                                    "type": "vulnerable_tech_version",
                                    "severity": severity,
                                    "technology": tech_name,
                                    "detected_version": version,
                                    "cve": cve,
                                    "description": description,
                                    "metasploit_available": has_msf,
                                })
                                identifiers.append(ident)

        severity_counts: dict[str, int] = {}
        for v in vulnerabilities:
            s = v.get("severity", "info")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "tech_detected": tech_detected,
            "vulnerabilities": vulnerabilities,
            "total_found": len(vulnerabilities),
            "severity_summary": severity_counts,
            "metasploit_exploitable": sum(
                1 for v in vulnerabilities if v.get("metasploit_available")
            ),
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
