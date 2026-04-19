"""OWASP Amass passive subdomain enumeration scanner with free API fallbacks."""

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


class AmassScanner(BaseOsintScanner):
    scanner_name = "amass"
    supported_input_types = frozenset({ScanInputType.DOMAIN})
    cache_ttl = 43200

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        domain = input_value.strip().lower()
        try:
            return await self._run_amass(domain)
        except FileNotFoundError:
            log.info("amass binary not found, falling back to free APIs", domain=domain)
            return await self._fallback_apis(domain)
        except Exception as exc:
            log.warning("amass subprocess failed, falling back", domain=domain, error=str(exc))
            return await self._fallback_apis(domain)

    async def _run_amass(self, domain: str) -> dict[str, Any]:
        domain_hash = hashlib.md5(domain.encode()).hexdigest()[:10]
        outfile = f"/tmp/amass_{domain_hash}.txt"

        proc = await asyncio.create_subprocess_exec(
            "amass", "enum",
            "-passive",
            "-d", domain,
            "-timeout", "60",
            "-o", outfile,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            await asyncio.wait_for(proc.communicate(), timeout=130)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            raise RuntimeError("amass timed out after 130s")

        subdomains: list[str] = []
        ips_found: list[str] = []
        outpath = Path(outfile)
        if outpath.exists():
            for line in outpath.read_text().splitlines():
                line = line.strip()
                if not line:
                    continue
                if _looks_like_ip(line):
                    ips_found.append(line)
                elif _is_subdomain_or_domain(line, domain):
                    subdomains.append(line.lower())
            try:
                outpath.unlink()
            except OSError:
                pass

        subdomains = list(dict.fromkeys(subdomains))
        ips_found = list(dict.fromkeys(ips_found))
        identifiers = [f"domain:{s}" for s in subdomains] + [f"ip:{ip}" for ip in ips_found]

        return {
            "input": domain,
            "found": bool(subdomains),
            "subdomains": subdomains,
            "ips_found": ips_found,
            "method": "amass",
            "total": len(subdomains),
            "extracted_identifiers": identifiers,
        }

    async def _fallback_apis(self, domain: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=20) as client:
            crt_task = asyncio.create_task(_fetch_crtsh(client, domain))
            rapiddns_task = asyncio.create_task(_fetch_rapiddns(client, domain))
            bufferover_task = asyncio.create_task(_fetch_bufferover(client, domain))

            crt_subs, rapiddns_subs, bufferover_data = await asyncio.gather(
                crt_task, rapiddns_task, bufferover_task, return_exceptions=True
            )

        all_subs: list[str] = []
        all_ips: list[str] = []

        if isinstance(crt_subs, list):
            all_subs.extend(crt_subs)
        if isinstance(rapiddns_subs, list):
            all_subs.extend(rapiddns_subs)
        if isinstance(bufferover_data, dict):
            all_subs.extend(bufferover_data.get("subdomains", []))
            all_ips.extend(bufferover_data.get("ips", []))

        unique_subs = list(dict.fromkeys(
            s.lower() for s in all_subs if _is_subdomain_or_domain(s, domain)
        ))
        unique_ips = list(dict.fromkeys(all_ips))
        identifiers = [f"domain:{s}" for s in unique_subs] + [f"ip:{ip}" for ip in unique_ips]

        return {
            "input": domain,
            "found": bool(unique_subs),
            "subdomains": unique_subs,
            "ips_found": unique_ips,
            "method": "fallback",
            "total": len(unique_subs),
            "extracted_identifiers": identifiers,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _looks_like_ip(value: str) -> bool:
    parts = value.split(".")
    if len(parts) != 4:
        return False
    return all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)


def _is_subdomain_or_domain(value: str, domain: str) -> bool:
    value = value.strip().lower()
    return value == domain or value.endswith(f".{domain}")


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
        log.debug("crt.sh fetch failed (amass fallback)", error=str(exc))
        return []


async def _fetch_rapiddns(client: httpx.AsyncClient, domain: str) -> list[str]:
    try:
        resp = await client.get(
            f"https://rapiddns.io/subdomain/{domain}",
            params={"full": "1"},
            headers={"User-Agent": "Mozilla/5.0 (compatible; OSINT-Scanner/1.0)"},
        )
        resp.raise_for_status()
        pattern = re.compile(r'<td>([a-zA-Z0-9._-]+\.' + re.escape(domain) + r')</td>')
        return list(dict.fromkeys(pattern.findall(resp.text)))
    except Exception as exc:
        log.debug("rapiddns fetch failed", error=str(exc))
        return []


async def _fetch_bufferover(client: httpx.AsyncClient, domain: str) -> dict[str, list[str]]:
    try:
        resp = await client.get(
            "https://dns.bufferover.run/dns",
            params={"q": f".{domain}"},
        )
        resp.raise_for_status()
        data = resp.json()
        subs: list[str] = []
        ips: list[str] = []
        for record in data.get("FDNS_A", []) + data.get("RDNS", []):
            parts = record.split(",")
            if len(parts) == 2:
                ip, host = parts[0].strip(), parts[1].strip()
                if _looks_like_ip(ip):
                    ips.append(ip)
                if host:
                    subs.append(host)
        return {"subdomains": subs, "ips": ips}
    except Exception as exc:
        log.debug("bufferover fetch failed", error=str(exc))
        return {"subdomains": [], "ips": []}
