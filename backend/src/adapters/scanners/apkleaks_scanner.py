"""APKLeaks scanner — scan APK files for hardcoded secrets and API endpoints."""

import asyncio
import hashlib
import json
import os
import re
import tempfile
import zipfile
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_MAX_APK_BYTES = 100 * 1024 * 1024  # 100 MB

_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("google_api_key", re.compile(r"AIza[0-9A-Za-z\-_]{35}")),
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("aws_secret_key", re.compile(r"[0-9a-zA-Z/+]{40}")),
    ("firebase_url", re.compile(r"[a-z0-9-]+\.firebaseio\.com")),
    ("private_key", re.compile(r"-----BEGIN (?:RSA|EC|DSA) PRIVATE KEY-----")),
    ("github_token", re.compile(r"ghp_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9_]{82}")),
    ("slack_token", re.compile(r"xox[baprs]-[0-9A-Za-z-]+")),
    ("email", re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")),
    ("ip_address", re.compile(r"\b(?:10|172\.(?:1[6-9]|2\d|3[01])|192\.168)\.[0-9.]+\b")),
]

_URL_PATTERN = re.compile(r"https?://[a-zA-Z0-9./?=_%:\-]+")
_EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

_SCANNABLE_EXTS = {".smali", ".xml", ".json", ".properties", ".yaml", ".yml", ".txt", ".gradle"}


class APKLeaksScanner(BaseOsintScanner):
    scanner_name = "apkleaks"
    supported_input_types = frozenset({ScanInputType.URL})
    cache_ttl = 86400

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        url = input_value.strip()
        content, size = await self._download_apk(url)
        if not content:
            return {
                "url": url,
                "found": False,
                "error": "Download failed or empty",
                "extracted_identifiers": [],
            }

        file_hash = hashlib.sha256(content[:8192]).hexdigest()[:16]
        tmp_path = os.path.join(tempfile.gettempdir(), f"apk_{file_hash}.apk")
        try:
            with open(tmp_path, "wb") as fh:
                fh.write(content)

            result = await self._try_apkleaks(tmp_path, file_hash)
            if result is None:
                result = self._manual_scan(content, tmp_path)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        identifiers: list[str] = []
        seen_domains: set[str] = set()
        for endpoint in result.get("endpoints_found", []):
            parsed = urlparse(endpoint)
            if parsed.netloc and parsed.netloc not in seen_domains:
                seen_domains.add(parsed.netloc)
                identifiers.append(f"url:{endpoint}")
        for email in result.get("emails_found", []):
            identifiers.append(f"email:{email}")

        result["url"] = url
        result["file_size_bytes"] = size
        result["extracted_identifiers"] = list(dict.fromkeys(identifiers))
        return result

    async def _download_apk(self, url: str) -> tuple[bytes, int]:
        try:
            async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
                async with client.stream("GET", url, headers={"User-Agent": "Mozilla/5.0"}) as resp:
                    if resp.status_code != 200:
                        return b"", 0
                    chunks: list[bytes] = []
                    total = 0
                    async for chunk in resp.aiter_bytes(65536):
                        chunks.append(chunk)
                        total += len(chunk)
                        if total >= _MAX_APK_BYTES:
                            break
                    return b"".join(chunks), total
        except Exception as exc:
            log.warning("APK download failed", url=url, error=str(exc))
            return b"", 0

    async def _try_apkleaks(self, apk_path: str, file_hash: str) -> dict[str, Any] | None:
        output_path = os.path.join(tempfile.gettempdir(), f"apkleaks_{file_hash}.json")
        try:
            proc = await asyncio.create_subprocess_exec(
                "python3", "-m", "apkleaks", "-f", apk_path, "-o", output_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=120)
            if os.path.exists(output_path):
                with open(output_path) as fh:
                    data = json.load(fh)
                secrets: list[dict[str, Any]] = []
                endpoints: list[str] = []
                emails: list[str] = []
                for key, values in data.items():
                    if isinstance(values, list):
                        for v in values:
                            if key.lower() in {"url", "endpoint"}:
                                endpoints.append(str(v))
                            elif "@" in str(v):
                                emails.append(str(v))
                            else:
                                secrets.append({"type": key, "value_preview": str(v)[:40], "file_path": ""})
                return {
                    "scan_method": "apkleaks",
                    "secrets_found": secrets,
                    "endpoints_found": list(dict.fromkeys(endpoints)),
                    "emails_found": list(dict.fromkeys(emails)),
                    "package_name": "",
                    "permissions": [],
                    "min_sdk": 0,
                }
        except (FileNotFoundError, asyncio.TimeoutError):
            return None
        except Exception as exc:
            log.debug("apkleaks subprocess error", error=str(exc))
            return None
        finally:
            try:
                os.unlink(output_path)
            except OSError:
                pass

    def _manual_scan(self, content: bytes, apk_path: str) -> dict[str, Any]:
        secrets: list[dict[str, Any]] = []
        endpoints: list[str] = []
        emails: list[str] = []
        package_name = ""
        permissions: list[str] = []
        min_sdk = 0

        if not zipfile.is_zipfile(apk_path):
            return {
                "scan_method": "manual_regex",
                "secrets_found": [],
                "endpoints_found": [],
                "emails_found": [],
                "package_name": "",
                "permissions": [],
                "min_sdk": 0,
                "error": "Not a valid ZIP/APK file",
            }

        try:
            with zipfile.ZipFile(apk_path, "r") as zf:
                for name in zf.namelist():
                    _, ext = os.path.splitext(name.lower())
                    if ext not in _SCANNABLE_EXTS:
                        continue
                    try:
                        file_content = zf.read(name).decode("utf-8", errors="replace")
                    except Exception:
                        continue

                    for secret_type, pattern in _SECRET_PATTERNS:
                        if secret_type == "email":
                            continue
                        for match in pattern.finditer(file_content):
                            val = match.group()
                            secrets.append({
                                "type": secret_type,
                                "value_preview": val[:40] + ("..." if len(val) > 40 else ""),
                                "file_path": name,
                            })

                    for m in _URL_PATTERN.finditer(file_content):
                        endpoints.append(m.group())
                    for m in _EMAIL_PATTERN.finditer(file_content):
                        emails.append(m.group())

                    if name == "AndroidManifest.xml":
                        pkg_match = re.search(r'package="([^"]+)"', file_content)
                        if pkg_match:
                            package_name = pkg_match.group(1)
                        permissions = re.findall(r'android\.permission\.([A-Z_]+)', file_content)
                        sdk_match = re.search(r'minSdkVersion="(\d+)"', file_content)
                        if sdk_match:
                            min_sdk = int(sdk_match.group(1))
        except Exception as exc:
            log.warning("APK manual scan error", error=str(exc))

        return {
            "scan_method": "manual_regex",
            "secrets_found": secrets[:200],
            "endpoints_found": list(dict.fromkeys(endpoints))[:200],
            "emails_found": list(dict.fromkeys(emails))[:100],
            "package_name": package_name,
            "permissions": list(dict.fromkeys(permissions)),
            "min_sdk": min_sdk,
        }
