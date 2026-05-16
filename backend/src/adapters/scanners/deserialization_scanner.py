"""Deserialization — unsafe object deserialization vulnerability scanner.

Detects Java (ysoserial gadget chains), PHP object injection (__PHP_Incomplete_Class),
Python pickle RCE, and .NET BinaryFormatter patterns via response analysis and
magic byte detection in endpoints that accept serialized data.
"""

from __future__ import annotations

import asyncio
import base64
import re
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Java serialized object magic bytes: AC ED 00 05
_JAVA_MAGIC_B64 = base64.b64encode(b"\xac\xed\x00\x05").decode()

# PHP object injection payloads
_PHP_PAYLOADS: list[tuple[str, str]] = [
    ('O:8:"stdClass":0:{}', "php_stdclass"),
    ('O:29:"__PHP_Incomplete_Class":0:{}', "php_incomplete_class"),
    ('a:1:{s:4:"test";O:8:"stdClass":0:{}}', "php_array_object"),
    ('O:8:"Exploit":1:{s:3:"cmd";s:2:"id";}', "php_exploit_class"),
]

# Python pickle REDUCE opcode header + benign cmd (lists modules)
_PICKLE_PAYLOADS: list[tuple[str, str]] = [
    # Base64 of a pickle that calls repr(os) — benign but triggers pickle parsing
    (base64.b64encode(b"\x80\x04\x95\x15\x00\x00\x00\x00\x00\x00\x00\x8c\x02os\x94\x8c\x06getpid\x94\x93\x94)\x81\x94.").decode(), "pickle_getpid"),
]

# .NET ViewState / BinaryFormatter patterns
_DOTNET_PATTERNS = re.compile(
    r"(?i)(AAEAAAD|__VIEWSTATE|__EVENTVALIDATION|YIBg|rNIAAA)",
    re.I,
)

# Endpoints likely to accept serialized data
_DESER_PATHS: list[str] = [
    "/", "/api", "/api/v1", "/deserialize", "/object",
    "/session", "/cache", "/data", "/payload",
    "/process", "/execute", "/run", "/invoke",
    "/rpc", "/remoting", "/service.asmx", "/Handler.ashx",
]

# Java gadget chain canary marker in response
_JAVA_CANARY = re.compile(
    r"(?i)(ysoserial|java\.io\.Serializable|ClassNotFoundException|"
    r"InvalidClassException|StreamCorruptedException|"
    r"java\.lang\.Runtime|java\.rmi\.|org\.apache\.commons\.collections)",
)

# PHP error patterns after injection
_PHP_ERROR_PATTERNS = re.compile(
    r"(?i)(unserialize\(\)|__wakeup|__destruct|__PHP_Incomplete_Class|"
    r"Object of class|allowed memory size|Fatal error)",
)

# Python error patterns
_PYTHON_DESER_PATTERNS = re.compile(
    r"(?i)(pickle\.loads|_reconstruct|AttributeError.*__reduce__|"
    r"copyreg|pickle\.UnpicklingError)",
)


class DeserializationScanner(BaseOsintScanner):
    """Unsafe deserialization vulnerability scanner.

    Tests for Java serialized object injection, PHP object injection,
    Python pickle deserialization, and .NET BinaryFormatter patterns.
    Analyzes endpoint responses to Java magic bytes, PHP serialize() format,
    and base64-encoded pickle streams.
    """

    scanner_name = "deserialization"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 3600
    scan_timeout = 90

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)
        return await self._manual_scan(base_url, input_value)

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []
        endpoints_tested: list[str] = []

        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; DeserScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(6)

            # Step 1: Detect serialization indicators in existing responses
            async def probe_endpoint(path: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + path
                    try:
                        resp = await client.get(url)
                        body = resp.text
                        content_type = resp.headers.get("content-type", "")

                        # Detect .NET ViewState / BinaryFormatter in HTML
                        if _DOTNET_PATTERNS.search(body):
                            match = _DOTNET_PATTERNS.search(body)
                            vulnerabilities.append({
                                "type": "dotnet_viewstate_detected",
                                "severity": "medium",
                                "url": url,
                                "evidence": match.group(0)[:40] if match else "",
                                "description": ".NET ViewState / BinaryFormatter serialization detected",
                                "remediation": "Enable ViewState MAC validation and use JSON serialization",
                            })
                            ident = "vuln:deserialization:dotnet_viewstate"
                            if ident not in identifiers:
                                identifiers.append(ident)

                        # Detect Java serialization in response
                        if _JAVA_CANARY.search(body):
                            match = _JAVA_CANARY.search(body)
                            vulnerabilities.append({
                                "type": "java_deserialization_indicator",
                                "severity": "high",
                                "url": url,
                                "evidence": match.group(0)[:60] if match else "",
                                "description": "Java serialization class references exposed in response",
                            })
                            ident = "vuln:deserialization:java_indicator"
                            if ident not in identifiers:
                                identifiers.append(ident)

                        if url not in endpoints_tested:
                            endpoints_tested.append(url)

                    except Exception:
                        pass

            await asyncio.gather(*[probe_endpoint(p) for p in _DESER_PATHS[:8]])

            # Step 2: Send PHP serialized payloads
            async def test_php_deser(path: str, payload: str, technique: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + path
                    try:
                        # POST as form data with serialized value
                        resp = await client.post(
                            url,
                            data={"data": payload, "object": payload, "payload": payload},
                            headers={"Content-Type": "application/x-www-form-urlencoded"},
                        )
                        body = resp.text

                        if _PHP_ERROR_PATTERNS.search(body):
                            match = _PHP_ERROR_PATTERNS.search(body)
                            vulnerabilities.append({
                                "type": "php_object_injection",
                                "severity": "critical",
                                "url": url,
                                "payload": payload[:80],
                                "technique": technique,
                                "evidence": match.group(0)[:60] if match else "",
                                "description": "PHP unserialize() triggered with injected object payload",
                                "cve": "CWE-502",
                            })
                            ident = f"vuln:deserialization:php:{technique}"
                            if ident not in identifiers:
                                identifiers.append(ident)

                    except Exception:
                        pass

            php_tasks = []
            for path in _DESER_PATHS[:4]:
                for payload, technique in _PHP_PAYLOADS[:2]:
                    php_tasks.append(test_php_deser(path, payload, technique))
            await asyncio.gather(*php_tasks)

            # Step 3: Java magic bytes injection
            async def test_java_deser(path: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + path
                    try:
                        java_payload = b"\xac\xed\x00\x05\x73\x72\x00\x04test"
                        resp = await client.post(
                            url,
                            content=java_payload,
                            headers={
                                "Content-Type": "application/octet-stream",
                                "X-Java-Serialized": "true",
                            },
                        )
                        body = resp.text

                        # 500 with Java exception = server tried to deserialize
                        if resp.status_code == 500 and _JAVA_CANARY.search(body):
                            match = _JAVA_CANARY.search(body)
                            vulnerabilities.append({
                                "type": "java_deserialization_rce",
                                "severity": "critical",
                                "url": url,
                                "evidence": match.group(0)[:60] if match else "",
                                "description": "Java deserialization endpoint triggered exception — likely vulnerable",
                                "cve": "CVE-2015-4852",
                                "remediation": "Implement deserialization filters (Java 9+ ObjectInputFilter)",
                            })
                            ident = "vuln:deserialization:java_rce"
                            if ident not in identifiers:
                                identifiers.append(ident)

                    except Exception:
                        pass

            await asyncio.gather(*[test_java_deser(p) for p in _DESER_PATHS[:4]])

            # Step 4: Python pickle probe (base64-encoded)
            async def test_pickle_deser(path: str, payload_b64: str, technique: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + path
                    try:
                        resp = await client.post(
                            url,
                            json={"data": payload_b64, "pickle": payload_b64, "serialized": payload_b64},
                        )
                        body = resp.text

                        if _PYTHON_DESER_PATTERNS.search(body):
                            match = _PYTHON_DESER_PATTERNS.search(body)
                            vulnerabilities.append({
                                "type": "python_pickle_injection",
                                "severity": "critical",
                                "url": url,
                                "technique": technique,
                                "evidence": match.group(0)[:60] if match else "",
                                "description": "Python pickle deserialization error exposed — RCE risk",
                                "cve": "CWE-502",
                                "remediation": "Replace pickle with JSON/msgpack; never deserialize untrusted data",
                            })
                            ident = f"vuln:deserialization:python:{technique}"
                            if ident not in identifiers:
                                identifiers.append(ident)

                    except Exception:
                        pass

            pickle_tasks = []
            for path in _DESER_PATHS[:3]:
                for payload_b64, technique in _PICKLE_PAYLOADS:
                    pickle_tasks.append(test_pickle_deser(path, payload_b64, technique))
            await asyncio.gather(*pickle_tasks)

        severity_counts: dict[str, int] = {}
        for v in vulnerabilities:
            s = v.get("severity", "info")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "endpoints_tested": len(endpoints_tested),
            "vulnerabilities": vulnerabilities,
            "total_found": len(vulnerabilities),
            "severity_summary": severity_counts,
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
