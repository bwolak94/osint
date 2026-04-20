"""Sublist3r-based subdomain enumeration scanner with free API fallbacks."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import tempfile
from pathlib import Path
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()


class Sublist3rScanner(BaseOsintScanner):
    scanner_name = "sublist3r"
    supported_input_types = frozenset({ScanInputType.DOMAIN})
    cache_ttl = 43200

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        domain = input_value.strip().lower()
        try:
            return await self._run_sublist3r(domain)
        except FileNotFoundError:
            log.info("sublist3r not available, falling back to free APIs", domain=domain)
            return await self._fallback_apis(domain)
        except Exception as exc:
            log.warning("sublist3r subprocess failed, falling back", domain=domain, error=str(exc))
            return await self._fallback_apis(domain)

    async def _run_sublist3r(self, domain: str) -> dict[str, Any]:
        domain_hash = hashlib.md5(domain.encode()).hexdigest()[:10]
        outfile = f"/tmp/sublist3r_{domain_hash}.txt"

        proc = await asyncio.create_subprocess_exec(
            "python3", "-m", "sublist3r",
            "-d", domain,
            "-o", outfile,
            "-v",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            await asyncio.wait_for(proc.communicate(), timeout=120)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            raise RuntimeError("sublist3r timed out after 120s")

        subdomains: list[str] = []
        outpath = Path(outfile)
        if outpath.exists():
            content = outpath.read_text()
            for line in content.splitlines():
                line = line.strip()
                if line and _is_subdomain(line, domain):
                    subdomains.append(line.lower())
            try:
                outpath.unlink()
            except OSError:
                pass

        subdomains = list(dict.fromkeys(subdomains))
        identifiers = [f"domain:{s}" for s in subdomains]

        return {
            "input": domain,
            "found": bool(subdomains),
            "subdomains": subdomains,
            "source_breakdown": {"sublist3r": len(subdomains)},
            "total_count": len(subdomains),
            "method": "sublist3r",
            "extracted_identifiers": identifiers,
        }

    async def _fallback_apis(self, domain: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20) as client:
            crt_task = asyncio.create_task(_fetch_crtsh(client, domain))
            hackertarget_task = asyncio.create_task(_fetch_hackertarget(client, domain))
            wayback_task = asyncio.create_task(_fetch_wayback_subdomains(client, domain))

            crt_subs, hackertarget_subs, wayback_subs = await asyncio.gather(
                crt_task, hackertarget_task, wayback_task, return_exceptions=True
            )

        source_breakdown: dict[str, int] = {}
        all_subs: list[str] = []

        if isinstance(crt_subs, list):
            source_breakdown["crt.sh"] = len(crt_subs)
            all_subs.extend(crt_subs)
        if isinstance(hackertarget_subs, list):
            source_breakdown["hackertarget"] = len(hackertarget_subs)
            all_subs.extend(hackertarget_subs)
        if isinstance(wayback_subs, list):
            source_breakdown["wayback"] = len(wayback_subs)
            all_subs.extend(wayback_subs)

        unique = list(dict.fromkeys(
            s.lower() for s in all_subs if _is_subdomain(s, domain)
        ))
        identifiers = [f"domain:{s}" for s in unique]

        return {
            "input": domain,
            "found": bool(unique),
            "subdomains": unique,
            "source_breakdown": source_breakdown,
            "total_count": len(unique),
            "method": "fallback_apis",
            "extracted_identifiers": identifiers,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_subdomain(value: str, domain: str) -> bool:
    value = value.strip().lower()
    return value.endswith(f".{domain}") or value == domain


async def _fetch_crtsh(client: httpx.AsyncClient, domain: str) -> list[str]:
    try:
        resp = await client.get(
            "https://crt.sh/",
            params={"q": f"%.{domain}", "output": "json"},
        )
        resp.raise_for_status()
        data = resp.json()
        subs: list[str] = []
        for entry in data:
            name = entry.get("name_value", "")
            for part in name.splitlines():
                part = part.strip().lstrip("*.")
                if part:
                    subs.append(part)
        return subs
    except Exception as exc:
        log.debug("crt.sh fetch failed", error=str(exc))
        return []


async def _fetch_hackertarget(client: httpx.AsyncClient, domain: str) -> list[str]:
    try:
        resp = await client.get(
            "https://api.hackertarget.com/hostsearch/",
            params={"q": domain},
        )
        resp.raise_for_status()
        subs: list[str] = []
        for line in resp.text.splitlines():
            if "," in line:
                host = line.split(",")[0].strip()
                if host:
                    subs.append(host)
        return subs
    except Exception as exc:
        log.debug("hackertarget fetch failed", error=str(exc))
        return []


async def _fetch_wayback_subdomains(client: httpx.AsyncClient, domain: str) -> list[str]:
    try:
        resp = await client.get(
            "https://web.archive.org/cdx/search/cdx",
            params={
                "url": f"*.{domain}",
                "output": "json",
                "fl": "original",
                "collapse": "urlkey",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        subs: list[str] = []
        for row in data[1:]:  # skip header row
            if row:
                url = row[0]
                host = _extract_host(url)
                if host:
                    subs.append(host)
        return subs
    except Exception as exc:
        log.debug("wayback subdomains fetch failed", error=str(exc))
        return []


def _extract_host(url: str) -> str:
    match = re.match(r"https?://([^/]+)", url)
    if match:
        return match.group(1).split(":")[0]
    return ""
