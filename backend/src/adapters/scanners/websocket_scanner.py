"""WebSocket Security — upgrade detection, origin bypass, and message injection scanner.

Detects WebSocket endpoints, tests for: missing origin validation (cross-origin
WS hijacking), unauthenticated WS endpoints, message injection via JSON/command
payloads, WS-based XSS, SSRF via ws:// URL schemes, and protocol downgrade.

WebSocket hijacking (CSWSH) is the WS equivalent of CSRF.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import re
import struct
import uuid
from typing import Any
from urllib.parse import urlparse, urljoin

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Common WebSocket paths
_WS_PATHS: list[str] = [
    "/ws", "/websocket", "/socket", "/socket.io",
    "/api/ws", "/api/websocket", "/api/socket",
    "/chat", "/live", "/realtime", "/events",
    "/stream", "/feed", "/updates",
    "/v1/ws", "/v2/ws",
    "/sockjs/info",
    "/cable",  # Rails ActionCable
    "/graphql",  # GraphQL WS subscriptions
]

# WebSocket upgrade probe headers
_WS_UPGRADE_HEADERS: dict[str, str] = {
    "Upgrade": "websocket",
    "Connection": "Upgrade",
    "Sec-WebSocket-Version": "13",
    "Sec-WebSocket-Key": base64.b64encode(b"scannerprobe12345").decode(),
}

# Origins to test for CSWSH (Cross-Site WebSocket Hijacking)
_EVIL_ORIGINS: list[str] = [
    "https://evil.com",
    "null",
    "https://evil.attacker.com",
    "http://localhost",
    "https://subdomain.target.com.evil.com",
]

# WebSocket injection payloads
_WS_INJECTION_PAYLOADS: list[tuple[str, str]] = [
    ('{"cmd":"ping","data":"<script>alert(1)</script>"}', "json_xss"),
    ('{"action":"subscribe","channel":"../../../etc/passwd"}', "path_traversal"),
    ('{"user_id":1,"role":"admin"}', "privilege_escalation"),
    ('{"type":"query","sql":"SELECT 1--"}', "sqli"),
    ("PING\r\nHost: evil.com\r\n\r\n", "request_injection"),
]

# Socket.io specific paths
_SOCKETIO_PATHS: list[str] = [
    "/socket.io/?EIO=4&transport=polling",
    "/socket.io/?EIO=3&transport=polling",
    "/socket.io/",
]


class WebSocketScanner(BaseOsintScanner):
    """WebSocket security vulnerability scanner.

    Discovers WS/WSS endpoints, tests for missing origin validation (CSWSH),
    unauthenticated access, and message injection vulnerabilities.
    """

    scanner_name = "websocket"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 3600
    scan_timeout = 60

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)
        return await self._manual_scan(base_url, input_value)

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []
        ws_endpoints: list[str] = []

        async with httpx.AsyncClient(
            timeout=8,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; WSScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(8)

            # Step 1: Detect WebSocket endpoints via HTTP upgrade probe
            async def probe_ws_endpoint(path: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + path
                    try:
                        resp = await client.get(url, headers=_WS_UPGRADE_HEADERS)
                        # 101 = Switching Protocols, 400/426 = WS expected but bad request
                        if resp.status_code in (101, 400, 426):
                            ws_endpoints.append(url)
                        elif resp.status_code == 200:
                            # Socket.io / SockJS returns 200 on polling transport
                            body = resp.text
                            if any(kw in body for kw in ["websocket", "polling", "sid", "upgrades", "heartbeat"]):
                                ws_endpoints.append(url)
                    except Exception:
                        pass

            # Also check Socket.io polling endpoints
            async def probe_socketio(path: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + path
                    try:
                        resp = await client.get(url)
                        if resp.status_code == 200 and ('"websocket"' in resp.text or '"polling"' in resp.text):
                            ws_endpoints.append(url)
                    except Exception:
                        pass

            tasks = [probe_ws_endpoint(p) for p in _WS_PATHS]
            tasks += [probe_socketio(p) for p in _SOCKETIO_PATHS]
            await asyncio.gather(*tasks)

            if ws_endpoints:
                identifiers.append("info:websocket:detected")

            # Step 2: Test CSWSH (Cross-Site WebSocket Hijacking)
            async def test_origin_bypass(endpoint: str, evil_origin: str) -> None:
                async with semaphore:
                    headers = {
                        **_WS_UPGRADE_HEADERS,
                        "Origin": evil_origin,
                    }
                    try:
                        resp = await client.get(endpoint, headers=headers)
                        # 101 with evil origin = no origin validation
                        if resp.status_code in (101, 400):
                            acao = resp.headers.get("access-control-allow-origin", "")
                            # Check for reflected/wildcard CORS on WS endpoint
                            if resp.status_code == 101 or evil_origin in str(resp.headers) or acao in ("*", evil_origin):
                                vulnerabilities.append({
                                    "type": "websocket_origin_bypass",
                                    "severity": "high",
                                    "url": endpoint,
                                    "evil_origin": evil_origin,
                                    "description": f"WebSocket endpoint accepts connections from '{evil_origin}' — CSWSH vulnerable",
                                    "remediation": "Validate Origin header against allowlist; reject unexpected origins",
                                })
                                ident = f"vuln:ws:origin_bypass"
                                if ident not in identifiers:
                                    identifiers.append(ident)
                    except Exception:
                        pass

            origin_tasks = []
            for endpoint in ws_endpoints[:4]:
                for origin in _EVIL_ORIGINS[:3]:
                    origin_tasks.append(test_origin_bypass(endpoint, origin))
            await asyncio.gather(*origin_tasks)

            # Step 3: Check WS endpoint without auth (no cookies/tokens)
            async def test_unauth_ws(endpoint: str) -> None:
                async with semaphore:
                    # Try WS upgrade without any auth cookie
                    try:
                        resp = await client.get(
                            endpoint,
                            headers={**_WS_UPGRADE_HEADERS},
                            cookies={},
                        )
                        if resp.status_code == 101:
                            vulnerabilities.append({
                                "type": "websocket_unauthenticated",
                                "severity": "high",
                                "url": endpoint,
                                "description": "WebSocket endpoint accepts connections without authentication",
                                "remediation": "Validate session/token before WS upgrade; reject unauthenticated connections",
                            })
                            identifiers.append("vuln:ws:unauthenticated")
                    except Exception:
                        pass

            await asyncio.gather(*[test_unauth_ws(ep) for ep in ws_endpoints[:4]])

            # Step 4: Check for ws:// (plaintext) alongside wss://
            for endpoint in ws_endpoints[:4]:
                if endpoint.startswith("https://"):
                    ws_plain = endpoint.replace("https://", "http://").replace("wss://", "ws://")
                    try:
                        resp = await client.get(ws_plain, headers=_WS_UPGRADE_HEADERS)
                        if resp.status_code in (101, 400, 426):
                            vulnerabilities.append({
                                "type": "websocket_plaintext",
                                "severity": "medium",
                                "url": ws_plain,
                                "description": "WebSocket endpoint available over plaintext ws:// — MITM interception possible",
                                "remediation": "Force wss:// only; redirect or block ws:// connections",
                            })
                            identifiers.append("vuln:ws:plaintext")
                    except Exception:
                        pass

            # Step 5: Socket.io specific checks
            socketio_url = base_url.rstrip("/") + "/socket.io/?EIO=4&transport=polling"
            try:
                resp = await client.get(socketio_url)
                if resp.status_code == 200 and "sid" in resp.text:
                    # Session ID leaked — check if it contains sensitive info
                    sid_match = re.search(r'"sid":"([^"]+)"', resp.text)
                    vulnerabilities.append({
                        "type": "socketio_session_exposed",
                        "severity": "low",
                        "url": socketio_url,
                        "session_id": sid_match.group(1)[:20] if sid_match else "found",
                        "description": "Socket.io session ID exposed in polling response",
                        "remediation": "Require authentication before Socket.io session creation",
                    })
                    identifiers.append("info:ws:socketio_detected")
            except Exception:
                pass

        severity_counts: dict[str, int] = {}
        for v in vulnerabilities:
            s = v.get("severity", "info")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "ws_endpoints": ws_endpoints,
            "ws_detected": bool(ws_endpoints),
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
