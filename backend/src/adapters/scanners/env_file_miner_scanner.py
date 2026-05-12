"""Environment File Miner — detect exposed .env and configuration files with secrets.

Module 46 in the Credential Intelligence domain. Probes for publicly accessible
environment and configuration files that often contain database credentials,
API keys, and other sensitive configuration.
"""

from __future__ import annotations

import re
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Files to probe
_ENV_PATHS: list[tuple[str, str]] = [
    ("/.env",                "Environment file"),
    ("/.env.local",          "Local environment file"),
    ("/.env.production",     "Production environment file"),
    ("/.env.staging",        "Staging environment file"),
    ("/.env.backup",         "Environment backup"),
    ("/config.php",          "PHP config file"),
    ("/wp-config.php",       "WordPress config"),
    ("/config/database.yml", "Rails database config"),
    ("/config/secrets.yml",  "Rails secrets"),
    ("/.aws/credentials",    "AWS credentials"),
    ("/credentials.json",    "Service account credentials"),
    ("/config.json",         "JSON config file"),
    ("/settings.py",         "Python settings"),
    ("/.npmrc",              "NPM registry config (may contain auth tokens)"),
    ("/.htpasswd",           "Apache password file"),
]

# Patterns that indicate a secret was found
_SECRET_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("AWS Access Key",        re.compile(r"AKIA[0-9A-Z]{16}")),
    ("AWS Secret Key",        re.compile(r"aws_secret_access_key\s*=\s*[A-Za-z0-9+/]{40}")),
    ("Database URL",          re.compile(r"(DATABASE_URL|DB_URL|SQLALCHEMY)\s*[=:]\s*\S+")),
    ("Password field",        re.compile(r"(PASSWORD|PASSWD|SECRET_KEY|JWT_SECRET)\s*[=:]\s*\S+", re.IGNORECASE)),
    ("API key",               re.compile(r"(API_KEY|APIKEY|API_SECRET)\s*[=:]\s*\S+", re.IGNORECASE)),
    ("Private key header",    re.compile(r"-----BEGIN (RSA |EC )?PRIVATE KEY-----")),
    ("Google API key",        re.compile(r"AIza[0-9A-Za-z\-_]{35}")),
    ("Generic token",         re.compile(r"(TOKEN|ACCESS_TOKEN|AUTH_TOKEN)\s*[=:]\s*\S+", re.IGNORECASE)),
]


def _detect_secrets(content: str) -> list[dict[str, str]]:
    """Detect secret patterns in file content. Returns redacted findings."""
    findings: list[dict[str, str]] = []
    for name, pattern in _SECRET_PATTERNS:
        match = pattern.search(content)
        if match:
            raw = match.group(0)[:80]
            # Redact the actual value after the = or : sign
            redacted = re.sub(r"([=:]\s*)(.{4}).*", r"\1\2****[REDACTED]", raw)
            findings.append({"type": name, "match_preview": redacted})
    return findings


class EnvFileMinerScanner(BaseOsintScanner):
    """Probe a domain for exposed environment and configuration files.

    Exposed .env files are among the most common and critical misconfigurations.
    They frequently contain production database passwords, API keys, and encryption
    secrets that provide immediate full-system compromise.
    """

    scanner_name = "env_file_miner"
    supported_input_types = frozenset({ScanInputType.DOMAIN})
    cache_ttl = 3600

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        domain = input_value.strip().rstrip("/")
        if not domain.startswith("http"):
            base_url = f"https://{domain}"
        else:
            base_url = domain

        exposed_files: list[dict[str, Any]] = []
        all_detected_secrets: list[dict[str, str]] = []

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=False,  # Don't follow — a redirect might mask the real response
            headers={"User-Agent": "Mozilla/5.0 (compatible; SecurityAudit/1.0)"},
        ) as client:
            for path, name in _ENV_PATHS:
                url = base_url + path
                try:
                    resp = await client.get(url)
                    # Only consider 200 responses with small bodies (likely real config, not error pages)
                    if resp.status_code == 200 and len(resp.content) < 100_000:
                        content = resp.text
                        # Heuristic: .env files have KEY=VALUE pattern
                        is_likely_env = (
                            path.endswith(".env") or
                            "=" in content or
                            ":" in content
                        ) and len(content) > 10
                        if is_likely_env:
                            secrets = _detect_secrets(content)
                            file_entry = {
                                "path": path,
                                "name": name,
                                "url": url,
                                "size_bytes": len(resp.content),
                                "detected_secrets": secrets,
                                "secret_count": len(secrets),
                            }
                            exposed_files.append(file_entry)
                            all_detected_secrets.extend(secrets)
                except Exception as exc:
                    log.debug("env_file_miner: probe failed", url=url, error=str(exc))

        found = len(exposed_files) > 0
        return {
            "found": found,
            "domain": domain,
            "total_exposed_files": len(exposed_files),
            "total_detected_secrets": len(all_detected_secrets),
            "exposed_files": exposed_files,
        }
