"""theHarvester-based email/host harvesting scanner with free source fallbacks."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


class TheHarvesterScanner(BaseOsintScanner):
    scanner_name = "theharvester"
    supported_input_types = frozenset({ScanInputType.DOMAIN})
    cache_ttl = 86400

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        domain = input_value.strip().lower()
        try:
            return await self._run_theharvester(domain)
        except FileNotFoundError:
            log.info("theHarvester not installed, falling back to free sources", domain=domain)
            return await self._fallback_sources(domain)
        except Exception as exc:
            log.warning(
                "theHarvester subprocess failed, falling back", domain=domain, error=str(exc)
            )
            return await self._fallback_sources(domain)

    async def _run_theharvester(self, domain: str) -> dict[str, Any]:
        domain_hash = hashlib.md5(domain.encode()).hexdigest()[:10]
        outbase = f"/tmp/harvester_{domain_hash}"

        proc = await asyncio.create_subprocess_exec(
            "theHarvester",
            "-d", domain,
            "-l", "100",
            "-b", "all",
            "-f", outbase,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=180)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            raise RuntimeError("theHarvester timed out after 180s")

        output_text = stdout.decode("utf-8", errors="replace")

        # Also try JSON output file if it was written
        json_path = Path(f"{outbase}.json")
        emails: list[str] = []
        hosts: list[str] = []
        ips: list[str] = []
        employees: list[str] = []
        sources: dict[str, list[str]] = {}

        if json_path.exists():
            try:
                data = json.loads(json_path.read_text())
                emails = data.get("emails", [])
                hosts = data.get("hosts", [])
                ips = data.get("ips", [])
                employees = data.get("people", [])
            except Exception:
                pass
            try:
                json_path.unlink()
            except OSError:
                pass
        else:
            # Parse from stdout
            emails = list(dict.fromkeys(_EMAIL_RE.findall(output_text)))
            hosts = list(dict.fromkeys(_extract_hosts(output_text, domain)))
            ips = list(dict.fromkeys(_extract_ips(output_text)))

        identifiers = _build_identifiers(emails, hosts, ips, employees)

        return {
            "input": domain,
            "found": bool(emails or hosts),
            "emails": emails,
            "hosts": hosts,
            "ips": ips,
            "employees": employees,
            "sources": sources,
            "method": "theharvester",
            "extracted_identifiers": identifiers,
        }

    async def _fallback_sources(self, domain: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20) as client:
            bing_task = asyncio.create_task(_scrape_bing_emails(client, domain))
            crt_task = asyncio.create_task(_fetch_crtsh_emails(client, domain))
            github_task = asyncio.create_task(_search_github(client, domain))
            ddg_task = asyncio.create_task(_scrape_ddg_linkedin(client, domain))

            results = await asyncio.gather(
                bing_task, crt_task, github_task, ddg_task, return_exceptions=True
            )

        bing_data = results[0] if isinstance(results[0], dict) else {}
        crt_data = results[1] if isinstance(results[1], dict) else {}
        github_data = results[2] if isinstance(results[2], dict) else {}
        ddg_data = results[3] if isinstance(results[3], dict) else {}

        all_emails: list[str] = []
        all_emails.extend(bing_data.get("emails", []))
        all_emails.extend(crt_data.get("emails", []))
        all_emails.extend(github_data.get("emails", []))

        all_hosts: list[str] = []
        all_ips: list[str] = []
        all_employees: list[str] = []
        all_employees.extend(ddg_data.get("employees", []))

        unique_emails = list(dict.fromkeys(
            e.lower() for e in all_emails if _EMAIL_RE.match(e)
        ))
        unique_hosts = list(dict.fromkeys(all_hosts))
        unique_ips = list(dict.fromkeys(all_ips))
        unique_employees = list(dict.fromkeys(all_employees))

        sources = {
            "bing": bing_data.get("emails", []),
            "crt_sh": crt_data.get("emails", []),
            "github": github_data.get("emails", []),
            "linkedin_ddg": ddg_data.get("employees", []),
        }

        identifiers = _build_identifiers(unique_emails, unique_hosts, unique_ips, unique_employees)

        return {
            "input": domain,
            "found": bool(unique_emails or unique_hosts),
            "emails": unique_emails,
            "hosts": unique_hosts,
            "ips": unique_ips,
            "employees": unique_employees,
            "sources": sources,
            "method": "fallback",
            "extracted_identifiers": identifiers,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_identifiers(
    emails: list[str],
    hosts: list[str],
    ips: list[str],
    employees: list[str],
) -> list[str]:
    ids: list[str] = []
    ids.extend(f"email:{e}" for e in emails)
    ids.extend(f"domain:{h}" for h in hosts)
    ids.extend(f"ip:{ip}" for ip in ips)
    ids.extend(f"person:{name}" for name in employees)
    return ids


def _extract_hosts(text: str, domain: str) -> list[str]:
    pattern = re.compile(r"([a-zA-Z0-9._-]+\." + re.escape(domain) + r")")
    return [m for m in pattern.findall(text) if m != domain]


def _extract_ips(text: str) -> list[str]:
    pattern = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
    return pattern.findall(text)


async def _scrape_bing_emails(client: httpx.AsyncClient, domain: str) -> dict[str, Any]:
    try:
        resp = await client.get(
            "https://www.bing.com/search",
            params={"q": f"@{domain}", "count": "50"},
            headers={"User-Agent": "Mozilla/5.0 (compatible; OSINT-Scanner/1.0)"},
        )
        resp.raise_for_status()
        emails = list(dict.fromkeys(
            e.lower() for e in _EMAIL_RE.findall(resp.text) if domain in e
        ))
        return {"emails": emails}
    except Exception as exc:
        log.debug("bing email scrape failed", error=str(exc))
        return {"emails": []}


async def _fetch_crtsh_emails(client: httpx.AsyncClient, domain: str) -> dict[str, Any]:
    try:
        resp = await client.get(
            "https://crt.sh/",
            params={"q": domain, "output": "json"},
        )
        resp.raise_for_status()
        text = resp.text
        emails = list(dict.fromkeys(
            e.lower() for e in _EMAIL_RE.findall(text) if domain in e
        ))
        return {"emails": emails}
    except Exception as exc:
        log.debug("crt.sh email fetch failed", error=str(exc))
        return {"emails": []}


async def _search_github(client: httpx.AsyncClient, domain: str) -> dict[str, Any]:
    try:
        resp = await client.get(
            "https://api.github.com/search/code",
            params={"q": f"{domain} in:file", "per_page": "10"},
            headers={"Accept": "application/vnd.github.v3+json"},
        )
        resp.raise_for_status()
        data = resp.json()
        text = str(data)
        emails = list(dict.fromkeys(
            e.lower() for e in _EMAIL_RE.findall(text) if domain in e
        ))
        return {"emails": emails}
    except Exception as exc:
        log.debug("github search failed", error=str(exc))
        return {"emails": []}


async def _scrape_ddg_linkedin(client: httpx.AsyncClient, domain: str) -> dict[str, Any]:
    try:
        resp = await client.get(
            "https://duckduckgo.com/html/",
            params={"q": f"site:linkedin.com/in {domain}"},
            headers={"User-Agent": "Mozilla/5.0 (compatible; OSINT-Scanner/1.0)"},
        )
        resp.raise_for_status()
        # Extract text snippets that look like names from LinkedIn results
        snippets = re.findall(
            r'result__snippet[^>]*>([^<]{10,100})', resp.text
        )
        employees: list[str] = []
        name_re = re.compile(r"\b([A-Z][a-z]+ [A-Z][a-z]+)\b")
        for snippet in snippets:
            for match in name_re.findall(snippet):
                employees.append(match)
        return {"employees": list(dict.fromkeys(employees))}
    except Exception as exc:
        log.debug("ddg linkedin scrape failed", error=str(exc))
        return {"employees": []}
