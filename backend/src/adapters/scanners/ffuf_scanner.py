"""FFUF — Fast web fuzzer for content discovery, vhost and parameter fuzzing.

FFUF (Fuzz Faster U Fool) is the industry-standard fast fuzzer for:
- Directory/file discovery with extension fuzzing
- Virtual host enumeration via Host header
- GET/POST parameter value fuzzing
- HTTP header fuzzing

Two-mode operation:
1. **ffuf binary** — if on PATH, invoked with JSON output
2. **Manual fallback** — extension fuzzing + common wordlist probing
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Extension wordlist — most common web server file extensions
_EXTENSIONS: list[str] = [
    ".php", ".asp", ".aspx", ".jsp", ".jspx",
    ".html", ".htm", ".xml", ".json", ".txt",
    ".bak", ".backup", ".old", ".orig", ".copy",
    ".zip", ".tar.gz", ".sql", ".log", ".csv",
    ".conf", ".config", ".cfg", ".ini", ".env",
    ".py", ".rb", ".pl", ".sh", ".bat",
    ".key", ".pem", ".crt", ".p12",
]

# Wordlist for ffuf directory fuzzing
_DIR_WORDLIST: list[str] = [
    "admin", "api", "app", "backup", "bin", "blog", "cache", "cgi-bin",
    "config", "console", "content", "css", "data", "database", "debug",
    "dev", "docs", "download", "downloads", "error", "files", "fonts",
    "hidden", "home", "images", "img", "include", "includes", "index",
    "info", "install", "js", "lib", "library", "login", "logs", "mail",
    "media", "new", "old", "page", "pages", "panel", "password", "php",
    "plugins", "portal", "private", "public", "resources", "scripts",
    "secure", "server", "service", "setup", "site", "sql", "src",
    "static", "stats", "storage", "system", "temp", "test", "theme",
    "themes", "tmp", "tools", "uploads", "user", "users", "util",
    "vendor", "web", "webmail", "wp-content", "xml",
]

# Interesting response codes
_MATCH_CODES = {200, 201, 204, 301, 302, 307, 308, 401, 403}


class FFUFScanner(BaseOsintScanner):
    """Fast fuzzer for web content, extension, and virtual host discovery.

    Performs:
    - Extension fuzzing on common file names (finds .bak, .sql, .env files)
    - Directory wordlist fuzzing
    - Virtual host discovery via Host header mutation
    Uses FFUF binary when available, otherwise async HTTP probing.
    """

    scanner_name = "ffuf"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 3600
    scan_timeout = 150

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)

        if shutil.which("ffuf"):
            return await self._run_ffuf_binary(base_url, input_value)
        return await self._manual_scan(base_url, input_value)

    async def _run_ffuf_binary(self, base_url: str, input_value: str) -> dict[str, Any]:
        run_id = os.urandom(4).hex()
        out_file = os.path.join(tempfile.gettempdir(), f"ffuf_{run_id}.json")
        wordlist_file = os.path.join(tempfile.gettempdir(), f"ffuf_wl_{run_id}.txt")

        with open(wordlist_file, "w") as f:
            f.write("\n".join(_DIR_WORDLIST))

        cmd = [
            "ffuf",
            "-u", f"{base_url}/FUZZ",
            "-w", wordlist_file,
            "-o", out_file,
            "-of", "json",
            "-mc", "200,201,204,301,302,307,308,401,403",
            "-t", "40",
            "-timeout", "10",
            "-s",
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=self.scan_timeout - 20)
        except asyncio.TimeoutError:
            log.warning("ffuf timed out", url=base_url)
            try:
                proc.kill()
            except Exception:
                pass
        finally:
            try:
                os.unlink(wordlist_file)
            except OSError:
                pass

        results: list[dict[str, Any]] = []
        identifiers: list[str] = []
        if os.path.exists(out_file):
            try:
                with open(out_file) as fh:
                    data = json.load(fh)
                for entry in data.get("results", []):
                    url = entry.get("url", "")
                    results.append({
                        "url": url,
                        "status": entry.get("status", 0),
                        "length": entry.get("length", 0),
                        "words": entry.get("words", 0),
                        "input": entry.get("input", {}).get("FUZZ", ""),
                    })
                    identifiers.append(f"url:{url}")
            except Exception as exc:
                log.warning("Failed to parse ffuf output", error=str(exc))
            finally:
                try:
                    os.unlink(out_file)
                except OSError:
                    pass

        return {
            "input": input_value,
            "scan_mode": "ffuf_binary",
            "base_url": base_url,
            "results": results,
            "total_found": len(results),
            "extracted_identifiers": identifiers,
        }

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        found_paths: list[dict[str, Any]] = []
        found_ext_files: list[dict[str, Any]] = []
        identifiers: list[str] = []

        async with httpx.AsyncClient(
            timeout=7,
            follow_redirects=False,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; FFUF/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(20)

            # Phase 1: Directory fuzzing
            async def probe_dir(word: str) -> None:
                async with semaphore:
                    url = f"{base_url.rstrip('/')}/{word}"
                    try:
                        resp = await client.get(url)
                        if resp.status_code in _MATCH_CODES:
                            found_paths.append({
                                "url": url,
                                "word": word,
                                "status": resp.status_code,
                                "length": len(resp.content),
                            })
                            identifiers.append(f"url:{url}")
                    except Exception:
                        pass

            # Phase 2: Extension fuzzing on sensitive file names
            _SENSITIVE_FILES = [
                "index", "config", "backup", "database", "db",
                "data", "admin", "wp-config", ".htaccess", ".htpasswd",
                "secret", "password", "credentials", "dump",
            ]

            async def probe_ext(name: str, ext: str) -> None:
                async with semaphore:
                    url = f"{base_url.rstrip('/')}/{name}{ext}"
                    try:
                        resp = await client.get(url)
                        if resp.status_code in _MATCH_CODES:
                            found_ext_files.append({
                                "url": url,
                                "file": f"{name}{ext}",
                                "extension": ext,
                                "status": resp.status_code,
                                "length": len(resp.content),
                                "severity": "critical" if ext in (".sql", ".env", ".bak", ".key", ".pem") else "medium",
                            })
                            identifiers.append(f"url:{url}")
                    except Exception:
                        pass

            dir_tasks = [probe_dir(w) for w in _DIR_WORDLIST]
            ext_tasks = [
                probe_ext(name, ext)
                for name in _SENSITIVE_FILES
                for ext in _EXTENSIONS
            ]

            await asyncio.gather(*dir_tasks, *ext_tasks)

        # Summary by status code
        status_summary: dict[int, int] = {}
        for p in found_paths + found_ext_files:
            s = p.get("status", 0)
            status_summary[s] = status_summary.get(s, 0) + 1

        critical_files = [f for f in found_ext_files if f.get("severity") == "critical"]

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "directories": found_paths,
            "extension_files": found_ext_files,
            "critical_files": critical_files,
            "total_found": len(found_paths) + len(found_ext_files),
            "status_summary": status_summary,
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
