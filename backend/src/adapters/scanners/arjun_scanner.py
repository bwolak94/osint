"""Arjun — HTTP parameter discovery scanner.

Discovers hidden GET/POST parameters on web endpoints. Critical for finding
hidden functionality, debug parameters, and injection points.

Two-mode operation:
1. **arjun binary** — if on PATH, invoked for full parameter discovery
2. **Manual fallback** — probes common parameters via GET and POST requests
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
from typing import Any
from urllib.parse import urlencode, urljoin, urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Common hidden/debug GET parameters to test
_COMMON_GET_PARAMS: list[str] = [
    "debug", "test", "dev", "admin", "verbose", "trace",
    "id", "user", "username", "uid", "email", "token",
    "key", "api_key", "apikey", "secret", "password", "pass",
    "redirect", "url", "next", "return", "callback", "ref",
    "action", "cmd", "command", "exec", "run",
    "file", "path", "dir", "include", "require",
    "format", "type", "output", "lang", "locale",
    "page", "offset", "limit", "skip", "count",
    "sort", "order", "filter", "search", "q", "query",
    "access_token", "auth", "session", "sid", "csrf",
    "preview", "draft", "version", "v",
    "source", "src", "data", "payload",
    "config", "conf", "setup", "install",
]

# Common POST body parameters
_COMMON_POST_PARAMS: list[str] = [
    "username", "password", "email", "user", "pass",
    "token", "api_key", "key", "secret",
    "name", "first_name", "last_name",
    "phone", "mobile", "address",
    "action", "type", "format",
    "data", "payload", "content",
    "id", "uid", "user_id",
    "redirect", "url", "next",
    "csrf_token", "_token", "nonce",
]


class ArjunScanner(BaseOsintScanner):
    """HTTP parameter discovery scanner.

    Probes endpoints for hidden GET/POST parameters by sending requests with
    common parameter names and analysing response differences. Useful for
    finding debug flags, hidden API functionality, and injection points.
    """

    scanner_name = "arjun"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 3600
    scan_timeout = 120

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)

        if shutil.which("arjun"):
            return await self._run_arjun_binary(base_url, input_value)
        return await self._manual_scan(base_url, input_value)

    async def _run_arjun_binary(self, base_url: str, input_value: str) -> dict[str, Any]:
        run_id = os.urandom(4).hex()
        out_file = os.path.join(tempfile.gettempdir(), f"arjun_{run_id}.json")
        cmd = [
            "arjun",
            "-u", base_url,
            "-oJ", out_file,
            "--stable",
            "-t", "10",
            "-q",
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=self.scan_timeout - 10)
        except asyncio.TimeoutError:
            log.warning("arjun timed out", url=base_url)
            try:
                proc.kill()
            except Exception:
                pass

        params_found: list[dict[str, Any]] = []
        if os.path.exists(out_file):
            try:
                with open(out_file) as fh:
                    data = json.load(fh)
                # Arjun JSON: [{url, params: [...]}, ...]
                for entry in data if isinstance(data, list) else [data]:
                    for param in entry.get("params", []):
                        params_found.append({
                            "url": entry.get("url", base_url),
                            "parameter": param,
                            "method": entry.get("method", "GET"),
                        })
            except Exception as exc:
                log.warning("Failed to parse arjun output", error=str(exc))
            finally:
                try:
                    os.unlink(out_file)
                except OSError:
                    pass

        identifiers = [f"param:{p['parameter']}" for p in params_found]
        return {
            "input": input_value,
            "scan_mode": "arjun_binary",
            "base_url": base_url,
            "parameters_found": params_found,
            "total_found": len(params_found),
            "extracted_identifiers": identifiers,
        }

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        """Manual parameter discovery by analysing response size variations."""
        params_found: list[dict[str, Any]] = []
        identifiers: list[str] = []

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ParamScanner/1.0)"},
        ) as client:
            # Baseline request — no params
            try:
                baseline = await client.get(base_url)
                baseline_len = len(baseline.content)
                baseline_status = baseline.status_code
            except Exception as exc:
                log.debug("Arjun baseline failed", url=base_url, error=str(exc))
                return {
                    "input": input_value,
                    "scan_mode": "manual_fallback",
                    "base_url": base_url,
                    "error": "Baseline request failed",
                    "parameters_found": [],
                    "extracted_identifiers": [],
                }

            semaphore = asyncio.Semaphore(10)

            async def test_get_param(param: str) -> None:
                async with semaphore:
                    try:
                        url = f"{base_url}?{param}=FUZZ_1337"
                        resp = await client.get(url)
                        content_len = len(resp.content)
                        # Significant size difference or status change = param reflected
                        size_diff = abs(content_len - baseline_len)
                        status_changed = resp.status_code != baseline_status
                        if size_diff > 50 or status_changed:
                            params_found.append({
                                "parameter": param,
                                "method": "GET",
                                "url": url,
                                "baseline_length": baseline_len,
                                "response_length": content_len,
                                "size_diff": size_diff,
                                "status_changed": status_changed,
                                "status_code": resp.status_code,
                            })
                            identifiers.append(f"param:{param}")
                    except Exception:
                        pass

            async def test_post_param(param: str) -> None:
                async with semaphore:
                    try:
                        resp = await client.post(base_url, data={param: "FUZZ_1337"})
                        # POST with unknown param — if 200 (vs 405/400) it accepts it
                        if resp.status_code not in (400, 405, 422, 501):
                            content_len = len(resp.content)
                            size_diff = abs(content_len - baseline_len)
                            if size_diff > 100 or resp.status_code == 200:
                                params_found.append({
                                    "parameter": param,
                                    "method": "POST",
                                    "url": base_url,
                                    "status_code": resp.status_code,
                                    "response_length": content_len,
                                })
                                if f"param:{param}" not in identifiers:
                                    identifiers.append(f"param:{param}")
                    except Exception:
                        pass

            get_tasks = [test_get_param(p) for p in _COMMON_GET_PARAMS]
            post_tasks = [test_post_param(p) for p in _COMMON_POST_PARAMS]
            await asyncio.gather(*get_tasks, *post_tasks)

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "parameters_found": params_found,
            "total_found": len(params_found),
            "interesting_params": list({p["parameter"] for p in params_found}),
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])


def _normalise_url(value: str, input_type: ScanInputType) -> str:
    if input_type == ScanInputType.DOMAIN:
        return f"https://{value}"
    if not value.startswith(("http://", "https://")):
        return f"https://{value}"
    return value.rstrip("/")
