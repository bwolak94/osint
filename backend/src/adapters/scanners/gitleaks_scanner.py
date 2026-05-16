"""Gitleaks — git secret and credential scanner.

Gitleaks detects hardcoded secrets, passwords, API keys and tokens in
git repositories and file systems using regex rules.

Two-mode operation:
1. **gitleaks binary** — if on PATH, invoked with JSON report output
2. **Manual fallback** — pattern-based scanning of web-exposed source files
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import tempfile
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Gitleaks-compatible high-signal secret rules
_LEAK_RULES: list[tuple[str, str, str]] = [
    # (rule_id, pattern, severity)
    ("aws-access-key-id", r"(?i)(A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}", "critical"),
    ("github-pat", r"ghp_[0-9a-zA-Z]{36}", "critical"),
    ("github-oauth", r"gho_[0-9a-zA-Z]{36}", "critical"),
    ("github-app-token", r"(ghu|ghs)_[0-9a-zA-Z]{36}", "critical"),
    ("github-refresh-token", r"ghr_[0-9a-zA-Z]{76}", "critical"),
    ("gitlab-pat", r"glpat-[0-9a-zA-Z\-]{20}", "critical"),
    ("heroku-api-key", r"(?i)heroku.*[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}", "high"),
    ("slack-bot-token", r"xoxb-[0-9]{11}-[0-9]{11}-[0-9a-zA-Z]{24}", "high"),
    ("slack-user-token", r"xoxp-[0-9]{11}-[0-9]{11}-[0-9]{11}-[0-9a-zA-Z]{32}", "high"),
    ("stripe-secret-key", r"sk_(live|test)_[0-9a-zA-Z]{24}", "critical"),
    ("stripe-publishable-key", r"pk_(live|test)_[0-9a-zA-Z]{24}", "medium"),
    ("twilio-account-sid", r"AC[a-zA-Z0-9_\-]{32}", "high"),
    ("sendgrid-api-key", r"SG\.[a-zA-Z0-9_\-]{22}\.[a-zA-Z0-9_\-]{43}", "high"),
    ("openai-api-key", r"sk-[a-zA-Z0-9]{48}", "critical"),
    ("google-api-key", r"AIza[0-9A-Za-z\-_]{35}", "high"),
    ("google-oauth", r"[0-9]+-[0-9A-Za-z_]{32}\.apps\.googleusercontent\.com", "medium"),
    ("firebase-url", r"(?i)(https://[a-z0-9.-]+\.firebaseio\.com)", "medium"),
    ("jwt-token", r"eyJ[A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=]+\.?[A-Za-z0-9\-_.+/=]*", "medium"),
    ("private-key", r"-----BEGIN (RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY", "critical"),
    ("generic-secret", r"(?i)(secret|password|passwd|pwd|token)\s*[=:]\s*['\"][A-Za-z0-9!@#$%^&*]{12,}", "medium"),
    ("database-url", r"(?i)(mysql|postgres|mongodb|redis|amqp)://[a-zA-Z0-9:@._/-]+", "high"),
]

# Source files to check for exposed secrets
_SOURCE_PATHS = [
    "/js/app.js",
    "/js/main.js",
    "/static/js/main.chunk.js",
    "/assets/index.js",
    "/bundle.js",
    "/app.bundle.js",
    "/.env.example",
    "/config/config.js",
    "/src/config.js",
    "/public/js/app.js",
]


class GitleaksScanner(BaseOsintScanner):
    """Git secret and credential scanner.

    Detects hardcoded secrets in git repositories using Gitleaks rules.
    In manual mode, checks for exposed JavaScript bundles and config files
    which commonly leak API keys and credentials.
    """

    scanner_name = "gitleaks"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 7200
    scan_timeout = 120

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)

        if shutil.which("gitleaks"):
            return await self._run_gitleaks_binary(base_url, input_value)
        return await self._manual_scan(base_url, input_value)

    async def _run_gitleaks_binary(self, base_url: str, input_value: str) -> dict[str, Any]:
        run_id = os.urandom(4).hex()
        out_file = os.path.join(tempfile.gettempdir(), f"gitleaks_{run_id}.json")
        cmd = [
            "gitleaks",
            "detect",
            "--source", ".",
            "--report-format", "json",
            "--report-path", out_file,
            "--no-banner",
            "--quiet",
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=self.scan_timeout - 10)
        except asyncio.TimeoutError:
            log.warning("gitleaks timed out")
            try:
                proc.kill()
            except Exception:
                pass

        leaks: list[dict[str, Any]] = []
        if os.path.exists(out_file):
            try:
                with open(out_file) as fh:
                    data = json.load(fh)
                for leak in data if isinstance(data, list) else []:
                    leaks.append({
                        "rule_id": leak.get("RuleID", ""),
                        "secret": (leak.get("Secret", "")[:15] + "...") if leak.get("Secret") else "",
                        "file": leak.get("File", ""),
                        "line": leak.get("StartLine", 0),
                        "commit": leak.get("Commit", ""),
                        "author": leak.get("Author", ""),
                        "date": leak.get("Date", ""),
                        "message": leak.get("Message", "")[:100],
                    })
            except Exception as exc:
                log.warning("Failed to parse gitleaks output", error=str(exc))
            finally:
                try:
                    os.unlink(out_file)
                except OSError:
                    pass

        identifiers = [f"secret:{l['rule_id']}" for l in leaks if l.get("rule_id")]
        return {
            "input": input_value,
            "scan_mode": "gitleaks_binary",
            "base_url": base_url,
            "leaks": leaks,
            "total_leaks": len(leaks),
            "unique_rules": list({l["rule_id"] for l in leaks if l.get("rule_id")}),
            "extracted_identifiers": identifiers,
        }

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        leaks: list[dict[str, Any]] = []
        identifiers: list[str] = []
        scanned_files: list[str] = []

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; GitleaksScanner/1.0)"},
        ) as client:
            # Try to find JavaScript bundles by checking the HTML source first
            try:
                resp = await client.get(base_url)
                if resp.status_code == 200:
                    # Extract JS file references from HTML
                    js_refs = re.findall(r'src=["\']([^"\']+\.js[^"\']*)["\']', resp.text)
                    for js_ref in js_refs[:5]:  # Check up to 5 JS files
                        if not js_ref.startswith("http"):
                            js_ref = base_url.rstrip("/") + "/" + js_ref.lstrip("/")
                        _SOURCE_PATHS.append(js_ref if js_ref.startswith("http") else js_ref)
            except Exception:
                pass

            for path in _SOURCE_PATHS:
                try:
                    target = path if path.startswith("http") else base_url.rstrip("/") + path
                    resp = await client.get(target)
                    if resp.status_code == 200 and len(resp.text) > 50:
                        content = resp.text
                        scanned_files.append(path if not path.startswith("http") else urlparse(path).path)
                        for rule_id, pattern, severity in _LEAK_RULES:
                            matches = re.findall(pattern, content)
                            for match in matches[:2]:  # Max 2 matches per rule per file
                                truncated = str(match)[:20] + "..." if len(str(match)) > 20 else str(match)
                                leak = {
                                    "rule_id": rule_id,
                                    "severity": severity,
                                    "evidence": truncated,
                                    "file": path if not path.startswith("http") else urlparse(path).path,
                                    "source": "web_exposed_file",
                                }
                                # Dedup by rule_id + file
                                key = f"{rule_id}:{leak['file']}"
                                existing_keys = {f"{l['rule_id']}:{l['file']}" for l in leaks}
                                if key not in existing_keys:
                                    leaks.append(leak)
                                    ident = f"secret:{rule_id}"
                                    if ident not in identifiers:
                                        identifiers.append(ident)
                except Exception:
                    pass

        severity_counts: dict[str, int] = {}
        for leak in leaks:
            s = leak.get("severity", "medium")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "leaks": leaks,
            "total_leaks": len(leaks),
            "scanned_files": scanned_files,
            "severity_summary": severity_counts,
            "unique_rules": list({l["rule_id"] for l in leaks if l.get("rule_id")}),
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
