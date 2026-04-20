"""IP allowlisting middleware."""
import ipaddress
from typing import Any

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

log = structlog.get_logger()


class IPAllowlistMiddleware(BaseHTTPMiddleware):
    """Restrict API access to configured IP ranges."""

    def __init__(self, app: Any, allowed_ips: list[str] | None = None, enabled: bool = False) -> None:
        super().__init__(app)
        self.enabled = enabled
        self.allowed_networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
        if allowed_ips:
            for ip_str in allowed_ips:
                try:
                    self.allowed_networks.append(ipaddress.ip_network(ip_str, strict=False))
                except ValueError:
                    log.warning("Invalid IP allowlist entry", ip=ip_str)

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if not self.enabled or not self.allowed_networks:
            return await call_next(request)

        client_ip = request.client.host if request.client else None
        if not client_ip:
            return await call_next(request)

        # Always allow health checks
        if request.url.path in ("/health", "/healthz", "/ready"):
            return await call_next(request)

        try:
            ip = ipaddress.ip_address(client_ip)
            if any(ip in network for network in self.allowed_networks):
                return await call_next(request)
        except ValueError:
            pass

        log.warning("IP not in allowlist", ip=client_ip)
        return JSONResponse(status_code=403, content={"detail": "Access denied: IP not in allowlist"})
