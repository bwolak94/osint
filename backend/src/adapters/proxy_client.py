"""OPSEC-aware HTTP client factory with Tor/SOCKS5 proxy support and user-agent rotation.

OPSEC threat model addressed:
- Direct requests leak your real IP to target services and any network observer.
- Consistent User-Agent fingerprints correlation across sessions.
- DNS leaks occur when the OS resolver is used instead of a privacy-preserving DoH.

This module provides:
  - make_http_client()  — factory returning a configured httpx.AsyncClient
  - verify_tor_connection() — validates Tor SOCKS5 is working before a scan run
  - ProxyMode enum       — DIRECT / TOR / SOCKS5 / ROTATING

Install optional dependency for proxy support:
    pip install httpx-socks
"""

from __future__ import annotations

import random
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import httpx
import structlog

if TYPE_CHECKING:
    pass

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Browser User-Agent pool (2024 vintage)
# ---------------------------------------------------------------------------

_USER_AGENTS: list[str] = [
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Chrome macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Firefox Linux
    "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
    # Firefox Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    # Safari macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    # Edge Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
]


class ProxyMode(StrEnum):
    """OPSEC anonymisation level for outbound requests."""

    DIRECT = "direct"       # No proxy — real IP exposed
    TOR = "tor"             # Tor SOCKS5 at localhost:9050
    SOCKS5 = "socks5"       # Custom SOCKS5 endpoint from settings
    ROTATING = "rotating"   # Cycle through a list of SOCKS5 proxies


def _resolve_proxy_url(mode: ProxyMode, socks5_url: str = "", proxy_pool: list[str] | None = None) -> str | None:
    """Return the SOCKS5 proxy URL string, or None for direct connections."""
    if mode == ProxyMode.DIRECT:
        return None
    if mode == ProxyMode.TOR:
        return "socks5://127.0.0.1:9050"
    if mode == ProxyMode.SOCKS5:
        return socks5_url or None
    if mode == ProxyMode.ROTATING and proxy_pool:
        return random.choice(proxy_pool)
    return None


def make_http_client(
    *,
    timeout: float = 20.0,
    proxy_mode: ProxyMode = ProxyMode.DIRECT,
    socks5_url: str = "",
    proxy_pool: list[str] | None = None,
    rotate_ua: bool = True,
    extra_headers: dict[str, str] | None = None,
    follow_redirects: bool = True,
    verify_ssl: bool = True,
) -> httpx.AsyncClient:
    """Create an OPSEC-configured httpx.AsyncClient.

    Args:
        timeout:          Total request timeout in seconds.
        proxy_mode:       Anonymisation mode (DIRECT, TOR, SOCKS5, ROTATING).
        socks5_url:       Custom SOCKS5 proxy URL (used when mode=SOCKS5).
        proxy_pool:       List of SOCKS5 URLs to randomly rotate (mode=ROTATING).
        rotate_ua:        Randomise User-Agent header for each client instantiation.
        extra_headers:    Additional request headers merged into defaults.
        follow_redirects: Follow HTTP 3xx redirects automatically.
        verify_ssl:       Verify TLS certificates (disable only for internal targets).

    Returns:
        Configured AsyncClient. Use as ``async with make_http_client() as client:``.

    Example::

        async with make_http_client(proxy_mode=ProxyMode.TOR) as client:
            resp = await client.get("https://check.torproject.org/api/ip")
    """
    # Default Accept headers that mimic a real browser
    headers: dict[str, str] = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
    }
    if rotate_ua:
        headers["User-Agent"] = random.choice(_USER_AGENTS)
    if extra_headers:
        headers.update(extra_headers)

    # Build proxy transport (requires httpx-socks)
    transport: httpx.AsyncBaseTransport | None = None
    proxy_url = _resolve_proxy_url(proxy_mode, socks5_url, proxy_pool)

    if proxy_url:
        try:
            import httpx_socks  # type: ignore[import-untyped]

            transport = httpx_socks.AsyncProxyTransport.from_url(
                proxy_url,
                rdns=True,           # Resolve DNS remotely (prevents DNS leaks)
                verify=verify_ssl,
            )
            log.debug("Proxy transport configured", mode=proxy_mode, url=proxy_url)
        except ImportError:
            log.warning(
                "httpx-socks not installed — using direct connection. "
                "Install with: pip install httpx-socks",
                requested_mode=proxy_mode,
            )

    return httpx.AsyncClient(
        transport=transport,
        timeout=httpx.Timeout(timeout),
        headers=headers,
        follow_redirects=follow_redirects,
        verify=verify_ssl,
    )


async def verify_tor_connection() -> dict[str, Any]:
    """Verify Tor SOCKS5 connectivity and confirm exit node IP.

    Returns:
        dict with keys: ``is_tor`` (bool), ``ip`` (str), ``error`` (str | None).
    """
    try:
        async with make_http_client(proxy_mode=ProxyMode.TOR, timeout=15) as client:
            resp = await client.get("https://check.torproject.org/api/ip")
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            is_tor: bool = data.get("IsTor", False)
            ip: str = data.get("IP", "unknown")
            log.info("Tor connectivity check", is_tor=is_tor, exit_ip=ip)
            return {"is_tor": is_tor, "ip": ip, "error": None}
    except Exception as exc:
        log.error("Tor connectivity check failed", error=str(exc))
        return {"is_tor": False, "ip": None, "error": str(exc)}


async def get_current_exit_ip(proxy_mode: ProxyMode = ProxyMode.DIRECT) -> str | None:
    """Return the public IP seen by target services under the current proxy mode."""
    try:
        async with make_http_client(proxy_mode=proxy_mode, timeout=10) as client:
            resp = await client.get("https://api.ipify.org?format=json")
            resp.raise_for_status()
            return resp.json().get("ip")
    except Exception as exc:
        log.warning("Exit IP check failed", error=str(exc))
        return None
