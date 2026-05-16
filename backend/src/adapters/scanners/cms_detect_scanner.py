"""CMS detection scanner — fingerprints CMS platform, version, and framework.

Identifies: WordPress, Joomla, Drupal, Magento, PrestaShop, OpenCart,
TYPO3, Ghost, Shopify, Squarespace, Wix, and custom frameworks.

Uses CMSeeK binary when available, otherwise performs HTTP-based fingerprinting.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import tempfile
from typing import Any
from urllib.parse import urljoin

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# CMS fingerprint signatures: (cms_name, type, pattern)
# type: "header", "body", "path"
_CMS_SIGNATURES: list[tuple[str, str, str]] = [
    # WordPress
    ("WordPress", "body", r"/wp-content/"),
    ("WordPress", "body", r"/wp-includes/"),
    ("WordPress", "body", r'<meta name="generator" content="WordPress'),
    ("WordPress", "header", r"wordpress"),
    # Joomla
    ("Joomla", "body", r"/components/com_"),
    ("Joomla", "body", r'<meta name="generator" content="Joomla'),
    ("Joomla", "body", r"/media/jui/"),
    # Drupal
    ("Drupal", "body", r"/sites/default/files/"),
    ("Drupal", "body", r"Drupal\.settings"),
    ("Drupal", "header", r"X-Generator.*Drupal"),
    ("Drupal", "body", r'<meta name="Generator" content="Drupal'),
    # Magento
    ("Magento", "body", r"/skin/frontend/"),
    ("Magento", "body", r"Mage\.Cookies"),
    ("Magento", "body", r"var BLANK_URL"),
    ("Magento", "header", r"X-Magento"),
    # PrestaShop
    ("PrestaShop", "body", r"/themes/default-bootstrap/"),
    ("PrestaShop", "body", r"prestashop"),
    ("PrestaShop", "header", r"PrestaShop"),
    # Shopify
    ("Shopify", "body", r"cdn\.shopify\.com"),
    ("Shopify", "body", r"Shopify\.theme"),
    # Squarespace
    ("Squarespace", "body", r"squarespace\.com"),
    ("Squarespace", "body", r"static\.squarespace\.com"),
    # Wix
    ("Wix", "body", r"static\.wix\.com"),
    ("Wix", "body", r"wix-sites\.com"),
    # TYPO3
    ("TYPO3", "body", r"/typo3/"),
    ("TYPO3", "body", r'<meta name="generator" content="TYPO3'),
    # Ghost
    ("Ghost", "body", r"ghost\.org"),
    ("Ghost", "body", r"/ghost/api/"),
    # Laravel
    ("Laravel", "header", r"X-Powered-By.*Laravel"),
    ("Laravel", "body", r"Illuminate\\"),
    # Django
    ("Django", "header", r"X-Frame-Options.*SAMEORIGIN"),
    ("Django", "body", r"csrfmiddlewaretoken"),
    # Ruby on Rails
    ("Ruby on Rails", "header", r"X-Powered-By.*Phusion Passenger"),
    ("Ruby on Rails", "body", r"data-remote=\"true\""),
    # OpenCart
    ("OpenCart", "body", r"/catalog/view/theme/"),
    ("OpenCart", "body", r"opencart"),
    # Webflow
    ("Webflow", "body", r"webflow\.com"),
    # HubSpot
    ("HubSpot", "body", r"hubspot\.com"),
    ("HubSpot", "header", r"X-HubSpot"),
]

# Version extraction patterns
_VERSION_PATTERNS: dict[str, list[str]] = {
    "WordPress": [
        r'<meta name="generator" content="WordPress ([0-9.]+)"',
        r"\?ver=([0-9.]+)",
    ],
    "Joomla": [
        r'<meta name="generator" content="Joomla! ([0-9.]+)"',
        r"Joomla! ([0-9.]+)",
    ],
    "Drupal": [
        r'<meta name="Generator" content="Drupal ([0-9.]+)',
        r'"drupal_version":"([0-9.]+)"',
    ],
}


class CMSDetectScanner(BaseOsintScanner):
    """CMS detection and fingerprinting scanner.

    Identifies the CMS/framework, version, server stack, and known security
    exposures for the target domain or URL.
    """

    scanner_name = "cms_detect"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 86400

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)

        if shutil.which("cmseek"):
            return await self._run_cmseek(base_url, input_value)
        return await self._fingerprint(base_url, input_value)

    async def _run_cmseek(self, base_url: str, input_value: str) -> dict[str, Any]:
        run_id = os.urandom(4).hex()
        out_dir = os.path.join(tempfile.gettempdir(), f"cmseek_{run_id}")
        os.makedirs(out_dir, exist_ok=True)
        cmd = ["cmseek", "--url", base_url, "--batch", "--follow-redirect",
               "--output-dir", out_dir, "--random-agent"]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=60)
        except asyncio.TimeoutError:
            log.warning("cmseek timed out", url=base_url)
            try:
                proc.kill()
            except Exception:
                pass

        result: dict[str, Any] = {
            "input": input_value,
            "scan_mode": "cmseek_binary",
            "base_url": base_url,
        }

        # Try to read CMSeeK JSON output
        for fname in ["cms_result.json", "result.json"]:
            fpath = os.path.join(out_dir, fname)
            if os.path.exists(fpath):
                try:
                    with open(fpath) as fh:
                        data = json.load(fh)
                    result.update({
                        "cms": data.get("cms_name"),
                        "cms_version": data.get("cms_version"),
                        "cms_url": data.get("cms_url"),
                        "vulnerabilities": data.get("vulnerabilities", []),
                    })
                    break
                except Exception as exc:
                    log.warning("Failed to parse CMSeeK output", error=str(exc))

        result["extracted_identifiers"] = []
        return result

    async def _fingerprint(self, base_url: str, input_value: str) -> dict[str, Any]:
        cms_votes: dict[str, int] = {}
        server_info: dict[str, str] = {}
        detected_frameworks: list[str] = []
        identifiers: list[str] = []
        version_map: dict[str, str] = {}

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; CMSDetect/1.0)"},
        ) as client:
            try:
                resp = await client.get(base_url)
                body = resp.text
                headers_str = " ".join(f"{k}: {v}" for k, v in resp.headers.items())

                for hdr in ["Server", "X-Powered-By", "X-Generator", "X-CMS"]:
                    val = resp.headers.get(hdr, "")
                    if val:
                        server_info[hdr] = val

                # Match CMS signatures
                for cms_name, sig_type, pattern in _CMS_SIGNATURES:
                    if sig_type == "body" and re.search(pattern, body, re.I):
                        cms_votes[cms_name] = cms_votes.get(cms_name, 0) + 1
                    elif sig_type == "header" and re.search(pattern, headers_str, re.I):
                        cms_votes[cms_name] = cms_votes.get(cms_name, 0) + 1

                # Try to extract version for detected CMS
                if cms_votes:
                    top_cms = max(cms_votes, key=lambda k: cms_votes[k])
                    for pat in _VERSION_PATTERNS.get(top_cms, []):
                        m = re.search(pat, body, re.I)
                        if m:
                            version_map[top_cms] = m.group(1)
                            break

            except Exception as exc:
                log.debug("CMS fingerprint request failed", url=base_url, error=str(exc))

            # Check specific CMS-confirming paths
            cms_paths = {
                "WordPress": "/wp-login.php",
                "Joomla": "/administrator/index.php",
                "Drupal": "/user/login",
                "Magento": "/admin",
                "PrestaShop": "/admin/",
            }
            for cms_name, path in cms_paths.items():
                if cms_votes.get(cms_name, 0) > 0:
                    try:
                        resp = await client.get(urljoin(base_url, path))
                        if resp.status_code in (200, 301, 302):
                            cms_votes[cms_name] = cms_votes.get(cms_name, 0) + 2
                            identifiers.append(f"url:{urljoin(base_url, path)}")
                    except Exception:
                        pass

        # Build result
        sorted_cms = sorted(cms_votes.items(), key=lambda kv: -kv[1])
        primary_cms = sorted_cms[0][0] if sorted_cms else None
        confidence = min(1.0, (sorted_cms[0][1] * 0.2)) if sorted_cms else 0.0

        return {
            "input": input_value,
            "scan_mode": "manual_fingerprint",
            "base_url": base_url,
            "cms_detected": primary_cms,
            "cms_version": version_map.get(primary_cms, "") if primary_cms else "",
            "confidence": round(confidence, 2),
            "all_candidates": [{"cms": k, "score": v} for k, v in sorted_cms],
            "server_info": server_info,
            "frameworks": detected_frameworks,
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
