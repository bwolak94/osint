"""Domain Squatting Detector — find typosquatting and lookalike domain registrations.

Module 48 in the Credential Intelligence domain. Generates character-substitution
and common typo variants of a target domain, then resolves which variants are
actually registered (have DNS A records). Used to detect brand impersonation,
phishing infrastructure, and typosquatting attacks.
"""

from __future__ import annotations

import asyncio
import socket
from typing import Any

import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()


def _extract_domain_parts(domain: str) -> tuple[str, str]:
    """Split 'example.com' into ('example', 'com')."""
    parts = domain.rsplit(".", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return domain, ""


def _generate_typos(name: str) -> list[str]:
    """Generate keyboard-adjacent typo variants for a domain name."""
    # Adjacent keys on QWERTY keyboard
    adjacent: dict[str, str] = {
        "a": "sqzw", "b": "vghn", "c": "xdfv", "d": "serfcx", "e": "wrsdf",
        "f": "drtgvc", "g": "ftyhbv", "h": "gyujnb", "i": "ujklo", "j": "huikmn",
        "k": "jiolm", "l": "kop", "m": "njk", "n": "bhjm", "o": "iklp",
        "p": "ol", "q": "wa", "r": "edft", "s": "awedxz", "t": "rfgy",
        "u": "yhji", "v": "cfgb", "w": "qase", "x": "zsdc", "y": "tghu",
        "z": "asx",
    }
    variants: list[str] = []

    # Character substitution
    for i, char in enumerate(name):
        for adj in adjacent.get(char.lower(), ""):
            variants.append(name[:i] + adj + name[i + 1:])

    # Missing character
    for i in range(len(name)):
        variants.append(name[:i] + name[i + 1:])

    # Doubled character
    for i, char in enumerate(name):
        variants.append(name[:i] + char + char + name[i + 1:])

    # Common homoglyphs and substitutions
    homoglyphs: dict[str, list[str]] = {
        "o": ["0"], "i": ["1", "l"], "l": ["1", "i"], "a": ["4"], "e": ["3"],
        "s": ["5"], "g": ["9"], "b": ["6"], "t": ["7"],
    }
    for i, char in enumerate(name):
        for sub in homoglyphs.get(char.lower(), []):
            variants.append(name[:i] + sub + name[i + 1:])

    # Common TLD-agnostic tricks
    variants.append(name + "s")
    variants.append(name + "-login")
    variants.append(name + "-secure")
    variants.append("www-" + name)
    variants.append(name.replace("-", ""))

    # Deduplicate and filter: exclude original name
    seen: set[str] = set()
    result: list[str] = []
    for v in variants:
        if v not in seen and v != name and len(v) >= 2:
            seen.add(v)
            result.append(v)
    return result


async def _resolve_domain(fqdn: str) -> bool:
    """Attempt DNS A record resolution. Returns True if registered."""
    loop = asyncio.get_event_loop()
    try:
        await asyncio.wait_for(
            loop.run_in_executor(None, socket.gethostbyname, fqdn),
            timeout=3.0,
        )
        return True
    except Exception:
        return False


class DomainSquattingScanner(BaseOsintScanner):
    """Detect registered typosquatting / lookalike domains.

    Generates ~80+ character-substitution variants of the target domain and
    resolves which ones are live. High hit rates indicate active brand impersonation
    campaigns used for phishing or credential harvesting.
    """

    scanner_name = "domain_squatting"
    supported_input_types = frozenset({ScanInputType.DOMAIN})
    cache_ttl = 3600

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        domain = input_value.strip().lower().lstrip("www.").rstrip("/")
        name, tld = _extract_domain_parts(domain)

        if not tld:
            return {"found": False, "domain": domain, "reason": "Could not parse domain parts"}

        typos = _generate_typos(name)
        common_tlds = [tld, "com", "net", "org", "co"] if tld not in ("com", "net", "org") else [tld]
        # Build candidate FQDNs
        candidates: list[str] = []
        for typo in typos[:40]:  # Limit to 40 typos
            for t in common_tlds[:2]:
                candidates.append(f"{typo}.{t}")

        # Cap total probes to 60 for performance
        candidates = list(dict.fromkeys(candidates))[:60]

        # Resolve concurrently
        semaphore = asyncio.Semaphore(20)

        async def check(fqdn: str) -> tuple[str, bool]:
            async with semaphore:
                return fqdn, await _resolve_domain(fqdn)

        results = await asyncio.gather(*[check(c) for c in candidates])
        registered = [fqdn for fqdn, is_live in results if is_live]

        # Risk scoring
        if len(registered) == 0:
            risk_level = "Low"
        elif len(registered) <= 3:
            risk_level = "Medium"
        elif len(registered) <= 10:
            risk_level = "High"
        else:
            risk_level = "Critical"

        return {
            "found": len(registered) > 0,
            "domain": domain,
            "total_checked": len(candidates),
            "total_registered": len(registered),
            "registered_squatters": registered[:30],  # Limit response size
            "risk_level": risk_level,
        }
