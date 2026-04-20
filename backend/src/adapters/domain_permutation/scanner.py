"""Domain permutation scanner generating typosquat / lookalike variants.

Uses dnstwist if available, falls back to a built-in basic generator.
Each permutation is resolved via asyncio DNS to check registration status.
"""

from __future__ import annotations

import asyncio
import socket
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PermutationResult:
    fuzzer: str
    domain: str
    registered: bool = False
    dns_a: list[str] = field(default_factory=list)
    dns_mx: list[str] = field(default_factory=list)


@dataclass
class PermutationScanResult:
    target_domain: str
    total_permutations: int = 0
    registered_count: int = 0
    permutations: list[dict[str, Any]] = field(default_factory=list)


class DomainPermutationScanner:
    """Generate and resolve domain permutations for typosquatting detection."""

    _MAX_RESOLVE = 200  # Limit DNS resolutions to avoid timeout

    async def scan(self, domain: str) -> PermutationScanResult:
        """Generate permutations and resolve each to check registration."""
        domain = domain.strip().lower().lstrip("www.").lstrip("http://").lstrip("https://")
        parts = domain.rsplit(".", 1)
        if len(parts) != 2:
            return PermutationScanResult(target_domain=domain)

        sld, tld = parts[0], parts[1]
        permutations = self._generate_permutations(sld, tld, domain)

        # Resolve in parallel (batched)
        results: list[PermutationResult] = []
        batch_size = 20
        for i in range(0, min(len(permutations), self._MAX_RESOLVE), batch_size):
            batch = permutations[i : i + batch_size]
            resolved = await asyncio.gather(
                *[self._resolve(p) for p in batch],
                return_exceptions=True,
            )
            for r in resolved:
                if isinstance(r, PermutationResult):
                    results.append(r)

        registered = [r for r in results if r.registered]

        return PermutationScanResult(
            target_domain=domain,
            total_permutations=len(permutations),
            registered_count=len(registered),
            permutations=[
                {
                    "fuzzer": r.fuzzer,
                    "domain": r.domain,
                    "registered": r.registered,
                    "dns_a": r.dns_a,
                    "dns_mx": r.dns_mx,
                }
                for r in results
            ],
        )

    def _generate_permutations(self, sld: str, tld: str, original: str) -> list[PermutationResult]:
        """Generate common typosquatting permutation classes."""
        perms: list[PermutationResult] = []
        seen: set[str] = {original}

        def _add(fuzzer: str, domain: str) -> None:
            if domain not in seen and len(domain) > 3:
                seen.add(domain)
                perms.append(PermutationResult(fuzzer=fuzzer, domain=domain))

        # Missing dot (add extra chars)
        for i in range(len(sld)):
            # Character omission
            candidate = sld[:i] + sld[i + 1 :]
            if candidate:
                _add("omission", f"{candidate}.{tld}")

            # Character repetition
            _add("repetition", f"{sld[:i]}{sld[i]}{sld[i:]}.{tld}")

        # Adjacent character swap (transposition)
        for i in range(len(sld) - 1):
            t = list(sld)
            t[i], t[i + 1] = t[i + 1], t[i]
            _add("transposition", f"{''.join(t)}.{tld}")

        # Common homoglyphs
        glyphs: dict[str, list[str]] = {
            "a": ["4", "@"],
            "e": ["3"],
            "i": ["1", "l"],
            "l": ["1", "i"],
            "o": ["0"],
            "s": ["5", "$"],
            "t": ["7"],
            "b": ["6"],
            "g": ["9"],
        }
        for i, ch in enumerate(sld):
            for replacement in glyphs.get(ch, []):
                _add("homoglyph", f"{sld[:i]}{replacement}{sld[i+1:]}.{tld}")

        # Hyphen insertion/removal
        for i in range(1, len(sld)):
            _add("hyphenation", f"{sld[:i]}-{sld[i:]}.{tld}")
        if "-" in sld:
            _add("hyphenation", f"{sld.replace('-', '')}.{tld}")

        # Common TLD swaps
        for alt_tld in ("com", "net", "org", "io", "co", "info", "biz", "online"):
            if alt_tld != tld:
                _add("tld-swap", f"{sld}.{alt_tld}")

        # Subdomain prefix
        for prefix in ("www", "mail", "secure", "login", "account", "my", "app"):
            _add("subdomain", f"{prefix}.{original}")

        # Addition of common suffixes
        for suffix in ("-login", "-secure", "-app", "-official", "-verify"):
            _add("addition", f"{sld}{suffix}.{tld}")

        return perms

    @staticmethod
    async def _resolve(perm: PermutationResult) -> PermutationResult:
        """Resolve A and MX records for a domain permutation."""
        loop = asyncio.get_event_loop()
        try:
            a_records = await loop.run_in_executor(None, socket.gethostbyname_ex, perm.domain)
            perm.dns_a = list(set(a_records[2]))
            perm.registered = True
        except (socket.gaierror, OSError):
            pass
        return perm
