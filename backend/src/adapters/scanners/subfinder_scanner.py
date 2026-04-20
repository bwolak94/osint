"""Subfinder-based passive subdomain enumeration scanner with free API fallbacks."""

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


class SubfinderScanner(BaseOsintScanner):
    scanner_name = "subfinder"
    supported_input_types = frozenset({ScanInputType.DOMAIN})
    cache_ttl = 43200

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        domain = input_value.strip().lower()
        try:
            return await self._run_subfinder(domain)
        except FileNotFoundError:
            log.info("subfinder not found, falling back to free APIs", domain=domain)
            return await self._fallback_apis(domain)
        except Exception as exc:
            log.warning("subfinder subprocess failed, falling back", domain=domain, error=str(exc))
            return await self._fallback_apis(domain)

    async def _run_subfinder(self, domain: str) -> dict[str, Any]:
        domain_hash = hashlib.md5(domain.encode()).hexdigest()[:10]
        outfile = f"/tmp/subfinder_{domain_hash}.txt"

        proc = await asyncio.create_subprocess_exec(
            "subfinder",
            "-d", domain,
            "-silent",
            "-o", outfile,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            await asyncio.wait_for(proc.communicate(), timeout=120)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            raise RuntimeError("subfinder timed out after 120s")

        subdomains: list[str] = []
        outpath = Path(outfile)
        if outpath.exists():
            for line in outpath.read_text().splitlines():
                line = line.strip().lower()
                if line and _is_subdomain_or_domain(line, domain):
                    subdomains.append(line)
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
            "source": "subfinder",
            "total": len(subdomains),
            "extracted_identifiers": identifiers,
        }

    async def _fallback_apis(self, domain: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20) as client:
            anubis_task = asyncio.create_task(_fetch_anubisdb(client, domain))
            crt_task = asyncio.create_task(_fetch_crtsh(client, domain))
            hackertarget_task = asyncio.create_task(_fetch_hackertarget(client, domain))
            threatcrowd_task = asyncio.create_task(_fetch_threatcrowd(client, domain))

            results = await asyncio.gather(
                anubis_task, crt_task, hackertarget_task, threatcrowd_task,
                return_exceptions=True,
            )

        all_subs: list[str] = []
        for result in results:
            if isinstance(result, list):
                all_subs.extend(result)

        unique = list(dict.fromkeys(
            s.lower() for s in all_subs if _is_subdomain_or_domain(s, domain)
        ))
        identifiers = [f"domain:{s}" for s in unique]

        return {
            "input": domain,
            "found": bool(unique),
            "subdomains": unique,
            "source": "fallback_apis",
            "total": len(unique),
            "extracted_identifiers": identifiers,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_subdomain_or_domain(value: str, domain: str) -> bool:
    value = value.strip().lower()
    return value == domain or value.endswith(f".{domain}")


async def _fetch_anubisdb(client: httpx.AsyncClient, domain: str) -> list[str]:
    try:
        resp = await client.get(f"https://jldc.me/anubis/subdomains/{domain}")
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            return [s for s in data if isinstance(s, str)]
        return []
    except Exception as exc:
        log.debug("anubisdb fetch failed", error=str(exc))
        return []


async def _fetch_crtsh(client: httpx.AsyncClient, domain: str) -> list[str]:
    try:
        resp = await client.get(
            "https://crt.sh/",
            params={"q": f"%.{domain}", "output": "json"},
        )
        resp.raise_for_status()
        subs: list[str] = []
        for entry in resp.json():
            name = entry.get("name_value", "")
            for part in name.splitlines():
                part = part.strip().lstrip("*.")
                if part:
                    subs.append(part)
        return subs
    except Exception as exc:
        log.debug("crt.sh fetch failed (subfinder fallback)", error=str(exc))
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
        log.debug("hackertarget fetch failed (subfinder fallback)", error=str(exc))
        return []


async def _fetch_threatcrowd(client: httpx.AsyncClient, domain: str) -> list[str]:
    try:
        resp = await client.get(
            "https://www.threatcrowd.org/searchApi/v2/domain/report/",
            params={"domain": domain},
        )
        resp.raise_for_status()
        data = resp.json()
        return [s for s in data.get("subdomains", []) if isinstance(s, str)]
    except Exception as exc:
        log.debug("threatcrowd fetch failed", error=str(exc))
        return []
