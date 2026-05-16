"""TruffleHog — secrets and credential detection in git repositories.

TruffleHog searches git history for high-entropy strings and regex patterns
that indicate leaked credentials, API keys, private keys, and secrets.

Two-mode operation:
1. **trufflehog binary** — if on PATH, full git history scanning with JSON output
2. **Manual fallback** — regex-based search of publicly accessible git objects
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import tempfile
from typing import Any
from urllib.parse import urlparse, urljoin

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# High-confidence secret regex patterns
_SECRET_PATTERNS: list[tuple[str, str, str]] = [
    # (pattern, secret_type, severity)
    (r"(?i)aws_access_key_id\s*[=:]\s*['\"]?AKIA[0-9A-Z]{16}", "aws_access_key", "critical"),
    (r"(?i)aws_secret_access_key\s*[=:]\s*['\"]?[A-Za-z0-9/+=]{40}", "aws_secret_key", "critical"),
    (r"(?i)(api.?key|apikey)\s*[=:]\s*['\"]?[A-Za-z0-9\-_]{20,}", "api_key", "high"),
    (r"(?i)(password|passwd|pwd)\s*[=:]\s*['\"]?[^\s'\",;]{8,}", "password", "high"),
    (r"(?i)(secret|private.?key)\s*[=:]\s*['\"]?[A-Za-z0-9\-_/+=]{16,}", "secret_key", "high"),
    (r"-----BEGIN (RSA|EC|DSA|OPENSSH) PRIVATE KEY-----", "private_key", "critical"),
    (r"(?i)github[_\s]?token\s*[=:]\s*['\"]?ghp_[A-Za-z0-9]{36}", "github_token", "critical"),
    (r"(?i)gitlab[_\s]?token\s*[=:]\s*['\"]?glpat-[A-Za-z0-9\-]{20}", "gitlab_token", "critical"),
    (r"sk-[A-Za-z0-9]{48}", "openai_api_key", "critical"),
    (r"(?i)database.?url\s*[=:]\s*['\"]?[a-z]+://[^'\"\s]+", "database_url", "high"),
    (r"(?i)(bearer|authorization)\s*[=:]\s*['\"]?[A-Za-z0-9\-_.]{20,}", "auth_token", "high"),
    (r"(?i)slack.?(api.?|webhook.?|bot.?)?token\s*[=:]\s*['\"]?xox[baprs]-[A-Za-z0-9\-]+", "slack_token", "high"),
    (r"(?i)stripe.?key\s*[=:]\s*['\"]?(sk|pk)_(test|live)_[A-Za-z0-9]{24,}", "stripe_key", "critical"),
    (r"(?i)twilio.?(account.?sid|auth.?token)\s*[=:]\s*['\"]?[A-Za-z0-9]{32,}", "twilio_credential", "high"),
    (r"(?i)jwt\s*[=:]\s*['\"]?eyJ[A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=]+\.?[A-Za-z0-9\-_.+/=]*", "jwt_token", "medium"),
    (r"(?i)smtp.?(password|pass|pwd)\s*[=:]\s*['\"]?[^\s'\",;]{6,}", "smtp_credential", "high"),
]

# Git URLs to check for exposed git data
_GIT_CHECK_PATHS = [
    "/.git/config",
    "/.git/HEAD",
    "/.git/COMMIT_EDITMSG",
    "/.git/packed-refs",
    "/.git/refs/heads/main",
    "/.git/refs/heads/master",
]


class TruffleHogScanner(BaseOsintScanner):
    """Secrets and credential detection scanner.

    Searches for leaked credentials, API keys, private keys, and high-entropy
    strings in git repositories and web application sources.
    """

    scanner_name = "trufflehog"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 7200
    scan_timeout = 120

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)

        if shutil.which("trufflehog"):
            return await self._run_trufflehog_binary(base_url, input_value)
        return await self._manual_scan(base_url, input_value)

    async def _run_trufflehog_binary(self, base_url: str, input_value: str) -> dict[str, Any]:
        cmd = [
            "trufflehog",
            "git",
            base_url,
            "--json",
            "--no-update",
            "--concurrency", "5",
        ]
        secrets: list[dict[str, Any]] = []
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            try:
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=self.scan_timeout - 10)
                for line in stdout.decode(errors="replace").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        secrets.append({
                            "detector_name": entry.get("DetectorName", "unknown"),
                            "verified": entry.get("Verified", False),
                            "raw_secret": entry.get("Raw", "")[:20] + "...",  # Truncate for safety
                            "commit": entry.get("SourceMetadata", {}).get("Data", {}).get("Git", {}).get("commit", ""),
                            "file": entry.get("SourceMetadata", {}).get("Data", {}).get("Git", {}).get("file", ""),
                            "severity": "critical" if entry.get("Verified") else "high",
                        })
                    except (json.JSONDecodeError, KeyError):
                        continue
            except asyncio.TimeoutError:
                log.warning("trufflehog timed out", url=base_url)
                try:
                    proc.kill()
                except Exception:
                    pass
        except Exception as exc:
            log.debug("trufflehog binary failed", error=str(exc))

        identifiers = [f"secret:{s['detector_name']}" for s in secrets]
        return {
            "input": input_value,
            "scan_mode": "trufflehog_binary",
            "base_url": base_url,
            "secrets_found": secrets,
            "total_secrets": len(secrets),
            "verified_secrets": sum(1 for s in secrets if s.get("verified")),
            "extracted_identifiers": identifiers,
        }

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        secrets_found: list[dict[str, Any]] = []
        identifiers: list[str] = []
        git_exposed = False
        exposed_git_files: list[str] = []

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=False,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; SecretScanner/1.0)"},
        ) as client:
            # 1. Check for exposed .git directory
            git_content_samples: list[str] = []
            for git_path in _GIT_CHECK_PATHS:
                try:
                    resp = await client.get(base_url.rstrip("/") + git_path)
                    if resp.status_code == 200 and len(resp.text) > 10:
                        git_exposed = True
                        exposed_git_files.append(git_path)
                        git_content_samples.append(resp.text[:2000])
                except Exception:
                    pass

            # 2. Check common config/env files for exposed secrets
            config_paths = [
                "/.env", "/.env.local", "/.env.production",
                "/config.php", "/wp-config.php",
                "/config/database.yml", "/config/secrets.yml",
                "/app/config/parameters.yml",
                "/settings.py", "/local_settings.py",
            ]
            for path in config_paths:
                try:
                    resp = await client.get(base_url.rstrip("/") + path)
                    if resp.status_code == 200 and len(resp.text) > 20:
                        git_content_samples.append(resp.text[:3000])
                        exposed_git_files.append(path)
                except Exception:
                    pass

            # 3. Search all collected content for secret patterns
            all_content = "\n".join(git_content_samples)
            for pattern, secret_type, severity in _SECRET_PATTERNS:
                matches = re.findall(pattern, all_content)
                for match in matches[:3]:  # Max 3 per type
                    truncated = str(match)[:30] + "..." if len(str(match)) > 30 else str(match)
                    finding = {
                        "secret_type": secret_type,
                        "severity": severity,
                        "evidence": truncated,
                        "note": "Found in exposed file — verify manually",
                    }
                    secrets_found.append(finding)
                    ident = f"secret:{secret_type}"
                    if ident not in identifiers:
                        identifiers.append(ident)

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "git_exposed": git_exposed,
            "exposed_files": exposed_git_files,
            "secrets_found": secrets_found,
            "total_secrets": len(secrets_found),
            "critical_count": sum(1 for s in secrets_found if s.get("severity") == "critical"),
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
