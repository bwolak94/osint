"""Banner grabber scanner — connects to common TCP ports and grabs service banners."""

import asyncio
from typing import Any

import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

_PORTS = [21, 22, 25, 80, 110, 143, 443, 3306, 3389, 5900, 8080]

_SERVICE_HINTS: dict[int, str] = {
    21: "ftp",
    22: "ssh",
    25: "smtp",
    80: "http",
    110: "pop3",
    143: "imap",
    443: "https",
    3306: "mysql",
    3389: "rdp",
    5900: "vnc",
    8080: "http-alt",
}


async def _grab_banner(host: str, port: int, timeout: float = 3.0) -> dict[str, Any] | None:
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        try:
            # Send a minimal probe to elicit a banner
            writer.write(b"\r\n")
            await writer.drain()
            data = await asyncio.wait_for(reader.read(1024), timeout=timeout)
            banner = data.decode("utf-8", errors="replace").strip()
        except Exception:
            banner = ""
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
        return {
            "port": port,
            "banner": banner[:500],
            "service_hint": _SERVICE_HINTS.get(port, "unknown"),
            "open": True,
        }
    except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
        return None


class BannerGrabberScanner(BaseOsintScanner):
    """Connects to common TCP ports and grabs service banners."""

    scanner_name = "banner_grabber"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.IP_ADDRESS})
    cache_ttl = 3600

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        tasks = [_grab_banner(input_value, port) for port in _PORTS]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        banners: list[dict[str, Any]] = []
        for result in results:
            if isinstance(result, dict):
                banners.append(result)

        open_ports = [b["port"] for b in banners]
        identifiers = [f"ip:{input_value}"] if input_type == ScanInputType.IP_ADDRESS else []

        return {
            "target": input_value,
            "found": len(banners) > 0,
            "open_ports": open_ports,
            "banners": banners,
            "extracted_identifiers": identifiers,
        }
