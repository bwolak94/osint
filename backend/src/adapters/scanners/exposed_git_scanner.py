"""Exposed .git directory scanner — detect publicly accessible git repositories.

Module 45 in the Credential Intelligence domain. Probes common git metadata paths
on a target domain to detect accidentally exposed source code repositories.
These exposures can reveal credentials, API keys, and business logic.
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Paths that confirm git repository exposure (ordered by severity)
_GIT_PATHS: list[tuple[str, str, str]] = [
    # (path, name, severity)
    ("/.git/HEAD",         "Git HEAD ref",        "critical"),
    ("/.git/config",       "Git config",          "critical"),
    ("/.git/COMMIT_EDITMSG","Git commit message",  "high"),
    ("/.git/index",        "Git index",           "high"),
    ("/.git/packed-refs",  "Git packed refs",     "medium"),
    ("/.git/logs/HEAD",    "Git log",             "medium"),
    ("/.gitignore",        ".gitignore",          "low"),
    ("/.git/description",  "Git description",     "low"),
]

_GIT_CONFIRM_STRINGS = [
    "ref: refs/",  # HEAD file content
    "[core]",      # config file content
    "Unnamed repository",  # description
]


class ExposedGitScanner(BaseOsintScanner):
    """Probe for exposed .git directories on web servers.

    An exposed .git directory allows an attacker to reconstruct the entire
    source code repository, including commit history, credentials in old commits,
    and internal documentation.
    """

    scanner_name = "exposed_git"
    supported_input_types = frozenset({ScanInputType.DOMAIN})
    cache_ttl = 3600

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        domain = input_value.strip().rstrip("/")
        if not domain.startswith("http"):
            # Try HTTPS first, then fall back will happen automatically
            base_url = f"https://{domain}"
        else:
            base_url = domain

        exposed_paths: list[dict[str, str]] = []
        is_git_confirmed = False
        highest_severity = "none"
        severity_order = {"critical": 4, "high": 3, "medium": 2, "low": 1, "none": 0}

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; SecurityAudit/1.0)"},
        ) as client:
            for path, name, severity in _GIT_PATHS:
                url = base_url + path
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        content = resp.text[:500]
                        # Confirm it's genuinely a git file, not a custom 200 page
                        is_git_content = any(s in content for s in _GIT_CONFIRM_STRINGS) or len(content) < 200
                        if is_git_content or path in ("/.git/HEAD", "/.git/config"):
                            exposed_paths.append({
                                "path": path,
                                "name": name,
                                "severity": severity,
                                "url": url,
                                "content_preview": content[:80],
                            })
                            if severity in ("critical", "high"):
                                is_git_confirmed = True
                            if severity_order[severity] > severity_order[highest_severity]:
                                highest_severity = severity
                except Exception as exc:
                    log.debug("exposed_git: probe failed", url=url, error=str(exc))

            # Try HTTP fallback if HTTPS had no results and is https
            if not exposed_paths and base_url.startswith("https"):
                http_base = base_url.replace("https://", "http://")
                for path, name, severity in _GIT_PATHS[:3]:  # Only check top 3 on fallback
                    url = http_base + path
                    try:
                        resp = await client.get(url)
                        if resp.status_code == 200:
                            content = resp.text[:500]
                            if any(s in content for s in _GIT_CONFIRM_STRINGS):
                                exposed_paths.append({
                                    "path": path,
                                    "name": name,
                                    "severity": severity,
                                    "url": url,
                                    "content_preview": content[:80],
                                })
                                if severity_order[severity] > severity_order[highest_severity]:
                                    highest_severity = severity
                    except Exception:
                        pass

        found = len(exposed_paths) > 0
        return {
            "found": found,
            "domain": domain,
            "is_git_confirmed": is_git_confirmed,
            "severity": highest_severity,
            "total_exposed": len(exposed_paths),
            "exposed_paths": exposed_paths,
            "recommendation": (
                "Immediately block access to /.git/ directory via web server configuration "
                "and rotate any credentials found in the repository history."
            ) if found else None,
        }
