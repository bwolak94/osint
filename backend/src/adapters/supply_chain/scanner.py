"""Software supply chain scanner.

Queries libraries.io API (or PyPI/npm directly) and OSV.dev for CVEs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class PackageResult:
    name: str
    registry: str  # npm/pypi/docker
    version: str | None = None
    downloads: int | None = None
    maintainer_emails: list[str] = field(default_factory=list)
    cves: list[dict[str, Any]] = field(default_factory=list)
    cve_count: int = 0
    risk_score: str = "low"


@dataclass
class SupplyChainScanResult:
    target: str
    target_type: str
    total_packages: int = 0
    total_cves: int = 0
    packages: list[dict[str, Any]] = field(default_factory=list)


class SupplyChainScanner:
    """Enumerate packages for a GitHub user/org and check OSV.dev for CVEs."""

    _OSV_URL = "https://api.osv.dev/v1/query"
    _GITHUB_URL = "https://api.github.com"
    _PYPI_URL = "https://pypi.org/pypi/{pkg}/json"
    _NPM_URL = "https://registry.npmjs.org/{pkg}"
    _TIMEOUT = 20.0

    def __init__(self) -> None:
        self._libraries_io_key = os.getenv("LIBRARIES_IO_API_KEY", "")

    async def scan(self, target: str, target_type: str) -> SupplyChainScanResult:
        result = SupplyChainScanResult(target=target, target_type=target_type)

        try:
            if target_type in ("github_user", "github_org"):
                packages = await self._get_github_packages(target)
            else:
                packages = await self._get_domain_packages(target)

            # Check each package against OSV.dev
            enriched: list[dict[str, Any]] = []
            for pkg in packages[:20]:  # Limit to 20 packages to avoid timeout
                cves = await self._check_osv(pkg["name"], pkg["registry"], pkg.get("version"))
                pkg["cves"] = cves
                pkg["cve_count"] = len(cves)
                pkg["risk_score"] = "critical" if len(cves) > 5 else "high" if len(cves) > 2 else "medium" if len(cves) > 0 else "low"
                enriched.append(pkg)

            result.packages = enriched
            result.total_packages = len(enriched)
            result.total_cves = sum(p["cve_count"] for p in enriched)

        except Exception as exc:
            result.packages = [{"name": f"Error: {exc}", "registry": "N/A", "version": None, "downloads": None, "maintainer_emails": [], "cves": [], "cve_count": 0, "risk_score": "unknown"}]

        return result

    async def _get_github_packages(self, username: str) -> list[dict[str, Any]]:
        """Get npm/pypi packages from GitHub repos."""
        packages: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=self._TIMEOUT) as client:
            resp = await client.get(
                f"{self._GITHUB_URL}/users/{username}/repos",
                params={"per_page": 30, "sort": "updated"},
                headers={"User-Agent": "OSINT-Platform/1.0", "Accept": "application/vnd.github.v3+json"},
            )
            if resp.status_code != 200:
                return packages

            repos = resp.json()
            for repo in repos[:10]:
                name = repo.get("name", "")
                # Check for package.json (npm)
                pkg_resp = await client.get(
                    f"{self._GITHUB_URL}/repos/{username}/{name}/contents/package.json",
                    headers={"User-Agent": "OSINT-Platform/1.0"},
                )
                if pkg_resp.status_code == 200:
                    packages.append({
                        "name": name,
                        "registry": "npm",
                        "version": None,
                        "downloads": None,
                        "maintainer_emails": [],
                    })
                    continue

                # Check for setup.py / pyproject.toml (pypi)
                for pyfile in ("setup.py", "pyproject.toml", "setup.cfg"):
                    py_resp = await client.get(
                        f"{self._GITHUB_URL}/repos/{username}/{name}/contents/{pyfile}",
                        headers={"User-Agent": "OSINT-Platform/1.0"},
                    )
                    if py_resp.status_code == 200:
                        packages.append({
                            "name": name,
                            "registry": "pypi",
                            "version": None,
                            "downloads": None,
                            "maintainer_emails": [],
                        })
                        break

        return packages

    async def _get_domain_packages(self, domain: str) -> list[dict[str, Any]]:
        """Search PyPI for packages matching the domain org name."""
        org = domain.split(".")[0]
        packages: list[dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=self._TIMEOUT) as client:
            # PyPI simple search (not officially supported but works for org names)
            resp = await client.get(
                f"https://pypi.org/simple/",
                headers={"User-Agent": "OSINT-Platform/1.0", "Accept": "application/vnd.pypi.simple.v1+json"},
            )
            if resp.status_code == 200:
                data = resp.json()
                matching = [p for p in data.get("projects", []) if org.lower() in p.get("name", "").lower()][:10]
                for pkg in matching:
                    packages.append({
                        "name": pkg["name"],
                        "registry": "pypi",
                        "version": None,
                        "downloads": None,
                        "maintainer_emails": [],
                    })

        return packages

    async def _check_osv(self, package_name: str, ecosystem: str, version: str | None) -> list[dict[str, Any]]:
        """Query OSV.dev for CVEs affecting this package."""
        ecosystem_map = {"npm": "npm", "pypi": "PyPI", "docker": "Docker"}
        osv_ecosystem = ecosystem_map.get(ecosystem.lower(), "PyPI")

        query: dict[str, Any] = {"package": {"name": package_name, "ecosystem": osv_ecosystem}}
        if version:
            query["version"] = version

        try:
            async with httpx.AsyncClient(timeout=self._TIMEOUT) as client:
                resp = await client.post(self._OSV_URL, json=query, headers={"User-Agent": "OSINT-Platform/1.0"})
                if resp.status_code != 200:
                    return []
                data = resp.json()

            return [
                {
                    "id": v.get("id"),
                    "summary": v.get("summary", ""),
                    "severity": (v.get("database_specific") or {}).get("severity", "UNKNOWN"),
                    "published": v.get("published"),
                }
                for v in data.get("vulns", [])[:10]
            ]
        except Exception:
            return []
