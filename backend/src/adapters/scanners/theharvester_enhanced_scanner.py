"""TheHarvester-enhanced scanner — multi-source email, subdomain, and employee harvesting."""

import asyncio
import hashlib
import re
import tempfile
import os
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_SUBDOMAIN_RE = re.compile(r"[\w\-]+(?:\.[\w\-]+)+\.[a-zA-Z]{2,}")
_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


class TheHarvesterEnhancedScanner(BaseOsintScanner):
    scanner_name = "theharvester_enhanced"
    supported_input_types = frozenset({ScanInputType.DOMAIN})
    cache_ttl = 86400

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        domain = input_value.strip().lower()

        result = await self._try_theharvester(domain)
        if result is not None:
            return result

        return await self._manual_harvest(domain)

    async def _try_theharvester(self, domain: str) -> dict[str, Any] | None:
        file_hash = hashlib.sha256(domain.encode()).hexdigest()[:16]
        output_base = os.path.join(tempfile.gettempdir(), f"harvester_{file_hash}")
        try:
            proc = await asyncio.create_subprocess_exec(
                "theHarvester",
                "-d", domain,
                "-l", "100",
                "-b", "bing,crtsh,dnsdumpster,hackertarget,urlscan",
                "-f", output_base,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
            if proc.returncode != 0:
                return None
            output = stdout.decode("utf-8", errors="replace")
            emails = list(dict.fromkeys(_EMAIL_RE.findall(output)))
            subdomains = list(dict.fromkeys(
                s for s in _SUBDOMAIN_RE.findall(output) if domain in s
            ))
            ips = list(dict.fromkeys(_IP_RE.findall(output)))
            identifiers = (
                [f"email:{e}" for e in emails]
                + [f"domain:{s}" for s in subdomains]
                + [f"ip:{ip}" for ip in ips]
            )
            return {
                "domain": domain,
                "scan_method": "theharvester",
                "emails": emails,
                "subdomains": subdomains,
                "ips": ips,
                "employees": [],
                "sources": {"theharvester": len(emails) + len(subdomains) + len(ips)},
                "extracted_identifiers": list(dict.fromkeys(identifiers)),
            }
        except (FileNotFoundError, asyncio.TimeoutError):
            return None
        except Exception as exc:
            log.debug("theHarvester subprocess error", domain=domain, error=str(exc))
            return None

    async def _manual_harvest(self, domain: str) -> dict[str, Any]:
        emails: list[str] = []
        subdomains: list[str] = []
        ips: list[str] = []
        employees: list[str] = []
        sources: dict[str, int] = {}

        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            results = await asyncio.gather(
                self._bing_search(client, domain),
                self._crtsh(client, domain),
                self._hackertarget(client, domain),
                self._urlscan(client, domain),
                self._github_search(client, domain),
                return_exceptions=True,
            )

        for i, source_name in enumerate(("bing", "crtsh", "hackertarget", "urlscan", "github")):
            if isinstance(results[i], BaseException):
                log.debug(f"Harvest source failed: {source_name}", error=str(results[i]))
                continue
            result: dict[str, Any] = results[i]  # type: ignore[assignment]
            e = result.get("emails", [])
            s = result.get("subdomains", [])
            ip = result.get("ips", [])
            emp = result.get("employees", [])
            emails.extend(e)
            subdomains.extend(s)
            ips.extend(ip)
            employees.extend(emp)
            sources[source_name] = len(e) + len(s) + len(ip)

        unique_emails = list(dict.fromkeys(emails))
        unique_subs = list(dict.fromkeys(subdomains))
        unique_ips = list(dict.fromkeys(ips))
        unique_employees = list(dict.fromkeys(employees))

        identifiers = (
            [f"email:{e}" for e in unique_emails]
            + [f"domain:{s}" for s in unique_subs]
            + [f"ip:{ip}" for ip in unique_ips]
            + [f"person:{p}" for p in unique_employees]
        )

        return {
            "domain": domain,
            "scan_method": "manual",
            "emails": unique_emails,
            "subdomains": unique_subs,
            "ips": unique_ips,
            "employees": unique_employees,
            "sources": sources,
            "extracted_identifiers": list(dict.fromkeys(identifiers)),
        }

    async def _bing_search(self, client: httpx.AsyncClient, domain: str) -> dict[str, Any]:
        emails: list[str] = []
        query = f'"{domain}" email'
        url = f"https://www.bing.com/search?q={query}&count=50"
        headers = {"User-Agent": "Mozilla/5.0 (compatible; OSINT-Scanner/1.0)"}
        try:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                emails = _EMAIL_RE.findall(resp.text)
                emails = [e for e in emails if domain in e]
        except Exception as exc:
            log.debug("Bing search failed", domain=domain, error=str(exc))
        return {"emails": list(dict.fromkeys(emails)), "subdomains": [], "ips": []}

    async def _crtsh(self, client: httpx.AsyncClient, domain: str) -> dict[str, Any]:
        subdomains: list[str] = []
        try:
            resp = await client.get(f"https://crt.sh/?q={domain}&output=json", timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                for entry in data:
                    name = entry.get("common_name", "")
                    if name and domain in name and not name.startswith("*"):
                        subdomains.append(name.lower().strip())
        except Exception as exc:
            log.debug("crt.sh failed", domain=domain, error=str(exc))
        return {"emails": [], "subdomains": list(dict.fromkeys(subdomains)), "ips": []}

    async def _hackertarget(self, client: httpx.AsyncClient, domain: str) -> dict[str, Any]:
        subdomains: list[str] = []
        ips: list[str] = []
        try:
            resp = await client.get(f"https://api.hackertarget.com/hostsearch/?q={domain}", timeout=15)
            if resp.status_code == 200:
                for line in resp.text.splitlines():
                    parts = line.split(",")
                    if len(parts) == 2:
                        subdomains.append(parts[0].strip())
                        ips.append(parts[1].strip())
        except Exception as exc:
            log.debug("HackerTarget failed", domain=domain, error=str(exc))
        return {"emails": [], "subdomains": subdomains, "ips": ips}

    async def _urlscan(self, client: httpx.AsyncClient, domain: str) -> dict[str, Any]:
        subdomains: list[str] = []
        try:
            resp = await client.get(
                f"https://urlscan.io/api/v1/search/?q=domain:{domain}&size=10",
                headers={"User-Agent": "OSINT-Platform/1.0"},
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                for result in data.get("results", []):
                    page = result.get("page", {})
                    dom = page.get("domain", "")
                    if dom and domain in dom:
                        subdomains.append(dom)
        except Exception as exc:
            log.debug("URLScan failed", domain=domain, error=str(exc))
        return {"emails": [], "subdomains": list(dict.fromkeys(subdomains)), "ips": []}

    async def _github_search(self, client: httpx.AsyncClient, domain: str) -> dict[str, Any]:
        emails: list[str] = []
        try:
            resp = await client.get(
                "https://api.github.com/search/code",
                params={"q": f"{domain} in:file extension:env", "per_page": "5"},
                headers={"User-Agent": "OSINT-Platform/1.0", "Accept": "application/vnd.github.v3+json"},
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("items", []):
                    name = item.get("name", "")
                    url_field = item.get("html_url", "")
                    emails.extend(_EMAIL_RE.findall(name + " " + url_field))
        except Exception as exc:
            log.debug("GitHub search failed", domain=domain, error=str(exc))
        return {"emails": list(dict.fromkeys(emails)), "subdomains": [], "ips": []}
