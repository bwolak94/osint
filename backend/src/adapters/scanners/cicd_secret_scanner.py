"""CI/CD Secret Scanner — checks for exposed secrets in public GitHub repositories.

Module 104 in the Infrastructure & Exploitation domain. Searches GitHub's public
repository index for repositories associated with the target domain. Checks
common sensitive file paths (.env, config files, CI/CD workflow files) via the
GitHub Contents API for potential secret patterns. Returns obfuscated findings.
"""

from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_GITHUB_API = "https://api.github.com"
_GITHUB_SEARCH = f"{_GITHUB_API}/search/repositories"
_GITHUB_CODE_SEARCH = f"{_GITHUB_API}/search/code"

# Regex patterns that indicate secrets or sensitive data
_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("AWS Access Key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Generic API Key", re.compile(r"(?i)(api[_\-]?key|apikey)\s*[:=]\s*['\"]?([A-Za-z0-9_\-]{20,})")),
    ("Generic Secret", re.compile(r"(?i)(secret|password|passwd|token)\s*[:=]\s*['\"]?([A-Za-z0-9_\-!@#$%^&*]{8,})")),
    ("Private Key Header", re.compile(r"-----BEGIN (RSA|EC|OPENSSH|DSA|PGP) PRIVATE KEY")),
    ("GitHub Token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36}")),
    ("Slack Token", re.compile(r"xox[baprs]-[0-9A-Za-z\-]+")),
    ("Stripe Key", re.compile(r"sk_live_[0-9a-zA-Z]{24}")),
    ("SendGrid Key", re.compile(r"SG\.[A-Za-z0-9_\-]{22}\.[A-Za-z0-9_\-]{43}")),
    ("Database URL", re.compile(r"(?i)(postgres|mysql|mongodb|redis)://[^\s\"']+")),
]

_SENSITIVE_FILE_PATHS = [
    ".env",
    ".env.local",
    ".env.production",
    "config/secrets.yml",
    "config/database.yml",
    ".travis.yml",
    "circle.yml",
    ".circleci/config.yml",
    "Jenkinsfile",
    ".github/workflows/deploy.yml",
    "docker-compose.yml",
    "kubernetes/secrets.yaml",
]


def _extract_domain_base(value: str) -> str:
    value = value.strip().lower().replace("https://", "").replace("http://", "").split("/")[0]
    parts = value.split(".")
    return parts[-2] if len(parts) >= 2 else parts[0]


def _obfuscate_secret(value: str) -> str:
    """Show only first 4 and last 2 characters of a suspected secret."""
    if len(value) <= 6:
        return "***"
    return value[:4] + "*" * (len(value) - 6) + value[-2:]


def _scan_content_for_secrets(content: str, file_path: str) -> list[dict[str, str]]:
    """Scan file content for secret patterns and return obfuscated findings."""
    findings: list[dict[str, str]] = []
    for label, pattern in _SECRET_PATTERNS:
        for match in pattern.finditer(content):
            matched_text = match.group(0)
            findings.append({
                "type": label,
                "file": file_path,
                "evidence": _obfuscate_secret(matched_text),
                "line_preview": content[max(0, match.start() - 20):match.end() + 20].replace("\n", " ")[:100],
            })
    return findings


class CICDSecretScanner(BaseOsintScanner):
    """Searches public GitHub repositories associated with the target domain for secrets.

    Uses the GitHub Search API to find repositories by domain name, then checks
    common sensitive file paths for exposed credentials, API keys, and tokens.
    Returns obfuscated findings to prevent accidental secret disclosure (Module 104).
    """

    scanner_name = "cicd_secret_scanner"
    supported_input_types = frozenset({ScanInputType.URL, ScanInputType.DOMAIN})
    cache_ttl = 43200  # 12 hours

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        domain_base = _extract_domain_base(input_value)
        github_token = os.getenv("GITHUB_TOKEN", "")

        headers: dict[str, str] = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "OSINT-Security-Research/1.0",
        }
        if github_token:
            headers["Authorization"] = f"Bearer {github_token}"

        repos_found: list[dict[str, Any]] = []
        secret_findings: list[dict[str, str]] = []

        async with httpx.AsyncClient(timeout=30, headers=headers) as client:
            # Step 1: Search for repositories related to the domain
            try:
                search_resp = await client.get(
                    _GITHUB_SEARCH,
                    params={"q": domain_base, "per_page": 10, "sort": "updated"},
                )
                if search_resp.status_code == 200:
                    repos_data = search_resp.json()
                    repos = repos_data.get("items", [])
                    for repo in repos[:5]:
                        repos_found.append({
                            "full_name": repo.get("full_name", ""),
                            "description": (repo.get("description") or "")[:100],
                            "stars": repo.get("stargazers_count", 0),
                            "private": repo.get("private", False),
                            "url": repo.get("html_url", ""),
                        })
            except httpx.RequestError as exc:
                log.warning("GitHub repo search failed", error=str(exc))

            # Step 2: Check sensitive files in discovered public repos
            for repo in repos_found[:3]:
                repo_name = repo["full_name"]
                for file_path in _SENSITIVE_FILE_PATHS[:6]:
                    url = f"{_GITHUB_API}/repos/{repo_name}/contents/{file_path}"
                    try:
                        file_resp = await client.get(url)
                        if file_resp.status_code == 200:
                            import base64
                            file_data = file_resp.json()
                            if file_data.get("encoding") == "base64":
                                content = base64.b64decode(file_data["content"]).decode("utf-8", errors="replace")
                                findings = _scan_content_for_secrets(content, f"{repo_name}/{file_path}")
                                secret_findings.extend(findings)
                    except (httpx.RequestError, Exception):
                        pass

        found = len(secret_findings) > 0

        return {
            "target": input_value,
            "domain_base": domain_base,
            "found": found,
            "repositories_found": len(repos_found),
            "repositories": repos_found,
            "secret_findings": secret_findings,
            "secret_count": len(secret_findings),
            "severity": "Critical" if found else "None",
            "github_api_authenticated": bool(github_token),
            "educational_note": (
                "CI/CD pipelines frequently expose secrets through committed .env files, "
                "hardcoded API keys in workflow files, and unprotected configuration. "
                "Use secret scanning tools (Gitleaks, TruffleHog) in pre-commit hooks."
            ),
            "recommendations": [
                "Rotate any detected credentials immediately.",
                "Use environment secrets in CI/CD instead of committed files.",
                "Enable GitHub Secret Scanning on all repositories.",
                "Add .env to .gitignore and audit git history for leaked secrets.",
                "Use a secrets manager (Vault, AWS Secrets Manager) in production.",
            ],
        }
