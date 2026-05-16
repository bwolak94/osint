"""Commix — command injection vulnerability scanner.

Commix (Command Injection Exploiter) is the go-to tool for detecting and
exploiting OS command injection vulnerabilities in web applications.

Two-mode operation:
1. **commix binary** — if on PATH, invoked in detection mode with JSON output
2. **Manual fallback** — probes parameters with OS command injection payloads
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import tempfile
from typing import Any
from urllib.parse import urlparse, parse_qs

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Command injection probes — (payload, technique, detection_pattern)
# Payloads use timing and out-of-band markers to avoid destructive execution
_CMDI_PROBES: list[tuple[str, str, str]] = [
    # Classic Unix/Linux command injection
    (";id", "semicolon", r"uid=\d+|gid=\d+|groups="),
    ("|id", "pipe", r"uid=\d+|gid=\d+|groups="),
    ("&&id", "ampersand", r"uid=\d+|gid=\d+|groups="),
    ("`id`", "backtick", r"uid=\d+|gid=\d+|groups="),
    ("$(id)", "dollar", r"uid=\d+|gid=\d+|groups="),
    # Windows command injection
    (";whoami", "semicolon_win", r"(?i)[a-z]+\\[a-z]+|AUTHORITY\\|Administrator"),
    ("|whoami", "pipe_win", r"(?i)[a-z]+\\[a-z]+|AUTHORITY\\|Administrator"),
    ("&&whoami", "ampersand_win", r"(?i)[a-z]+\\[a-z]+|AUTHORITY\\|Administrator"),
    # Time-based blind (sleep 2s)
    ("; sleep 2", "time_blind", None),
    ("& ping -c 2 127.0.0.1", "time_blind", None),
    # Encoded variants
    ("%3Bid", "encoded_semicolon", r"uid=\d+|gid=\d+"),
    ("%7Cid", "encoded_pipe", r"uid=\d+|gid=\d+"),
    ("%26%26id", "encoded_ampersand", r"uid=\d+|gid=\d+"),
]

# Common parameters that feed into OS commands (file ops, ping, email, etc.)
_CMDI_PARAMS: list[str] = [
    "host", "ip", "url", "domain", "target",
    "file", "path", "dir", "filename", "filepath",
    "cmd", "command", "exec", "run", "query",
    "ping", "trace", "nslookup", "dig",
    "email", "to", "from", "subject",
    "input", "data", "value", "param",
    "test", "check", "verify", "validate",
    "name", "user", "username",
]


class CommixScanner(BaseOsintScanner):
    """OS command injection vulnerability scanner.

    Tests web application parameters for command injection vulnerabilities
    using semicolon, pipe, ampersand, backtick, and encoding-based techniques.
    Includes time-based blind detection for cases with no output reflection.
    """

    scanner_name = "commix"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 1800
    scan_timeout = 120

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)

        if shutil.which("commix"):
            return await self._run_commix_binary(base_url, input_value)
        return await self._manual_scan(base_url, input_value)

    async def _run_commix_binary(self, base_url: str, input_value: str) -> dict[str, Any]:
        run_id = os.urandom(4).hex()
        out_file = os.path.join(tempfile.gettempdir(), f"commix_{run_id}.json")
        cmd = [
            "commix",
            "--url", base_url,
            "--batch",
            "--output-dir", os.path.dirname(out_file),
            "--log-file", out_file,
            "--level", "2",
            "--timeout", "8",
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=self.scan_timeout - 10)
        except asyncio.TimeoutError:
            log.warning("commix timed out", url=base_url)
            try:
                proc.kill()
            except Exception:
                pass

        vulnerabilities: list[dict[str, Any]] = []
        if os.path.exists(out_file):
            try:
                with open(out_file) as fh:
                    content = fh.read()
                for match in re.finditer(
                    r"Parameter '(\S+)' appears to be '([^']+)' injectable", content
                ):
                    vulnerabilities.append({
                        "parameter": match.group(1),
                        "technique": match.group(2),
                        "severity": "critical",
                    })
            except Exception as exc:
                log.warning("Failed to parse commix output", error=str(exc))
            finally:
                try:
                    os.unlink(out_file)
                except OSError:
                    pass

        identifiers = [f"vuln:cmdi:{v['parameter']}" for v in vulnerabilities]
        return {
            "input": input_value,
            "scan_mode": "commix_binary",
            "base_url": base_url,
            "vulnerabilities": vulnerabilities,
            "total_found": len(vulnerabilities),
            "extracted_identifiers": identifiers,
        }

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        time_based_suspects: list[dict[str, Any]] = []
        identifiers: list[str] = []

        parsed = urlparse(base_url)
        existing_params = list(parse_qs(parsed.query).keys())
        base_clean = base_url.split("?")[0]
        test_params = list(dict.fromkeys(existing_params + _CMDI_PARAMS[:8]))

        async with httpx.AsyncClient(
            timeout=12,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; CommixScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(5)

            async def test_param(param: str) -> None:
                async with semaphore:
                    # Baseline timing
                    try:
                        import time
                        t0 = time.monotonic()
                        await client.get(f"{base_clean}?{param}=test_value_1337")
                        baseline_time = time.monotonic() - t0
                    except Exception:
                        baseline_time = 1.0

                    for payload, technique, pattern in _CMDI_PROBES:
                        try:
                            # Skip time-based in parallel — test separately
                            if technique == "time_blind":
                                continue
                            test_url = f"{base_clean}?{param}={payload}"
                            resp = await client.get(test_url)
                            body = resp.text
                            if pattern and re.search(pattern, body):
                                vuln = {
                                    "parameter": param,
                                    "payload": payload,
                                    "technique": technique,
                                    "severity": "critical",
                                    "evidence": re.search(pattern, body).group(0)[:50] if re.search(pattern, body) else "",
                                    "description": f"OS command output reflected in response",
                                }
                                vulnerabilities.append(vuln)
                                ident = f"vuln:cmdi:{param}"
                                if ident not in identifiers:
                                    identifiers.append(ident)
                                return  # Confirmed — skip other payloads
                        except Exception:
                            pass

                    # Time-based blind test (sequential, not parallel)
                    for payload, technique, _ in _CMDI_PROBES:
                        if technique != "time_blind":
                            continue
                        try:
                            import time
                            t0 = time.monotonic()
                            await client.get(f"{base_clean}?{param}={payload}")
                            elapsed = time.monotonic() - t0
                            # Sleep payload adds ~2s — detect if response took significantly longer
                            if elapsed > baseline_time + 1.5 and elapsed > 2.0:
                                time_based_suspects.append({
                                    "parameter": param,
                                    "payload": payload,
                                    "technique": "time_based_blind",
                                    "severity": "high",
                                    "evidence": f"Response delayed {elapsed:.1f}s vs baseline {baseline_time:.1f}s",
                                })
                                ident = f"vuln:cmdi_blind:{param}"
                                if ident not in identifiers:
                                    identifiers.append(ident)
                                break
                        except Exception:
                            pass

            tasks = [test_param(p) for p in test_params]
            await asyncio.gather(*tasks)

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "vulnerabilities": vulnerabilities,
            "time_based_suspects": time_based_suspects,
            "total_confirmed": len(vulnerabilities),
            "total_suspected": len(time_based_suspects),
            "params_tested": test_params,
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])


def _normalise_url(value: str, input_type: ScanInputType) -> str:
    if input_type == ScanInputType.DOMAIN:
        return f"https://{value}"
    if not value.startswith(("http://", "https://")):
        return f"https://{value}"
    return value
