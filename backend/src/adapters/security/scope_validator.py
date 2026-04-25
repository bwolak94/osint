"""Scope validator — enforces engagement rules-of-engagement boundaries.

Prevents pentest tools from targeting out-of-scope hosts, private networks,
cloud metadata endpoints, and any explicitly excluded targets.

Geofencing (EU Dual-Use Regulation 2021/821):
  When GEOFENCE_ALLOWED_COUNTRIES env var is set (comma-separated ISO-3166-1
  alpha-2 codes, e.g. "PL,DE,FR"), any target IP whose country is NOT in that
  list raises a ScopeViolation.  Uses ip-api.com (free, no API key required).
  Set to empty string to disable geofencing.
"""

import ipaddress
import os
import socket
from dataclasses import dataclass, field
from typing import List


HARD_BLOCKED_CIDRS: List[str] = [
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "127.0.0.0/8",
    "169.254.0.0/16",
    "100.64.0.0/10",
    "::1/128",
    "fc00::/7",
    "fe80::/10",
]

CLOUD_METADATA_IPS: List[str] = [
    "169.254.169.254",   # AWS / GCP / Azure IMDS
    "fd00:ec2::254",      # AWS IPv6 IMDS
    "168.63.129.16",      # Azure IMDS
    "100.100.100.200",    # Alibaba Cloud IMDS
]


class ScopeViolation(Exception):
    """Raised when a target falls outside the allowed engagement scope."""


@dataclass
class ScopeRules:
    allowed_cidrs: List[str] = field(default_factory=list)
    allowed_domains: List[str] = field(default_factory=list)
    excluded: List[str] = field(default_factory=list)


def _parse_network(cidr: str) -> ipaddress.IPv4Network | ipaddress.IPv6Network:
    return ipaddress.ip_network(cidr, strict=False)


def _ip_in_networks(
    addr: ipaddress.IPv4Address | ipaddress.IPv6Address,
    networks: List[str],
) -> bool:
    for net_str in networks:
        try:
            net = _parse_network(net_str)
            if addr in net:
                return True
        except ValueError:
            continue
    return False


def _resolve_to_ips(host: str) -> List[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Resolve hostname to IP addresses; return empty list on failure."""
    try:
        results = socket.getaddrinfo(host, None)
        ips = []
        for item in results:
            try:
                ips.append(ipaddress.ip_address(item[4][0]))
            except ValueError:
                continue
        return ips
    except (socket.gaierror, OSError):
        return []


def _get_allowed_countries() -> frozenset[str]:
    """Return the set of ISO-3166-1 alpha-2 country codes allowed by geofence.

    Returns an empty frozenset if geofencing is disabled (env var not set or empty).
    """
    raw = os.environ.get("GEOFENCE_ALLOWED_COUNTRIES", "").strip()
    if not raw:
        return frozenset()
    return frozenset(c.strip().upper() for c in raw.split(",") if c.strip())


async def check_geofence(ip_str: str) -> None:
    """Raise ScopeViolation if the IP's country is outside the allowed geofence.

    No-ops if GEOFENCE_ALLOWED_COUNTRIES is not configured.
    Skips RFC1918 / loopback addresses (they have no country).
    """
    allowed = _get_allowed_countries()
    if not allowed:
        return  # Geofencing disabled

    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return  # Not a bare IP — let domain validation handle it

    # Skip private / loopback addresses
    if addr.is_private or addr.is_loopback or addr.is_link_local:
        return

    try:
        import httpx  # noqa: PLC0415
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"http://ip-api.com/json/{ip_str}?fields=countryCode,status")
            data = resp.json()
    except Exception:
        # Network error — fail open (do not block if geo check unavailable)
        return

    if data.get("status") != "success":
        return  # Unknown IP — fail open

    country = (data.get("countryCode") or "").upper()
    if country and country not in allowed:
        raise ScopeViolation(
            f"Target IP {ip_str} is located in {country!r}, which is outside the "
            f"allowed geofence ({', '.join(sorted(allowed))}). "
            "EU Dual-Use Regulation 2021/821 compliance check failed."
        )


class ScopeValidator:
    """Validates whether a target is within the engagement's rules-of-engagement."""

    def __init__(self, rules: ScopeRules) -> None:
        self._rules = rules
        self._blocked_networks = [_parse_network(c) for c in HARD_BLOCKED_CIDRS]
        self._cloud_ips = {ipaddress.ip_address(ip) for ip in CLOUD_METADATA_IPS}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_ip(self, ip_str: str) -> None:
        """Raise ScopeViolation if the IP address is not in scope."""
        try:
            addr = ipaddress.ip_address(ip_str)
        except ValueError as exc:
            raise ScopeViolation(f"Invalid IP address: {ip_str!r}") from exc

        self._check_hard_blocks(addr)
        self._check_cloud_metadata(addr)
        self._check_excluded_ip(addr)

        if not self._rules.allowed_cidrs:
            raise ScopeViolation("No allowed CIDRs defined in scope rules.")

        if not _ip_in_networks(addr, self._rules.allowed_cidrs):
            raise ScopeViolation(
                f"IP {ip_str} is not within any allowed CIDR: {self._rules.allowed_cidrs}"
            )

    def validate_domain(self, domain: str) -> None:
        """Raise ScopeViolation if the domain is not in scope."""
        self._check_excluded_domain(domain)

        if self._domain_explicitly_allowed(domain):
            # Resolve and check resolved IPs against hard blocks
            for ip in _resolve_to_ips(domain):
                self._check_hard_blocks(ip)
                self._check_cloud_metadata(ip)
            return

        # Fall back to checking if resolved IP is in allowed CIDRs
        resolved = _resolve_to_ips(domain)
        if not resolved:
            raise ScopeViolation(
                f"Domain {domain!r} could not be resolved and is not explicitly allowed."
            )

        for ip in resolved:
            self._check_hard_blocks(ip)
            self._check_cloud_metadata(ip)

        if self._rules.allowed_cidrs:
            if any(_ip_in_networks(ip, self._rules.allowed_cidrs) for ip in resolved):
                return

        raise ScopeViolation(
            f"Domain {domain!r} resolves to IPs not within any allowed CIDR or domain list."
        )

    def validate_cidr(self, cidr: str) -> None:
        """Raise ScopeViolation if the CIDR block is not fully within scope."""
        try:
            network = ipaddress.ip_network(cidr, strict=False)
        except ValueError as exc:
            raise ScopeViolation(f"Invalid CIDR: {cidr!r}") from exc

        # Check first and last address of the block
        for addr in (network.network_address, network.broadcast_address):
            self._check_hard_blocks(addr)
            self._check_cloud_metadata(addr)

        if not self._rules.allowed_cidrs:
            raise ScopeViolation("No allowed CIDRs defined in scope rules.")

        for allowed_str in self._rules.allowed_cidrs:
            try:
                allowed_net = _parse_network(allowed_str)
                if network.subnet_of(allowed_net):  # type: ignore[arg-type]
                    return
            except ValueError:
                continue

        raise ScopeViolation(f"CIDR {cidr} is not a subnet of any allowed CIDR.")

    def validate_url(self, url: str) -> None:
        """Raise ScopeViolation if the URL's host is not in scope."""
        from urllib.parse import urlparse

        parsed = urlparse(url)
        host = parsed.hostname
        if not host:
            raise ScopeViolation(f"Cannot extract host from URL: {url!r}")

        try:
            # Direct IP in URL
            addr = ipaddress.ip_address(host)
            self.validate_ip(str(addr))
        except ValueError:
            # Hostname
            self.validate_domain(host)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_hard_blocks(
        self, addr: ipaddress.IPv4Address | ipaddress.IPv6Address
    ) -> None:
        for net in self._blocked_networks:
            if addr in net:
                raise ScopeViolation(
                    f"Address {addr} is in hard-blocked private/reserved range {net}."
                )

    def _check_cloud_metadata(
        self, addr: ipaddress.IPv4Address | ipaddress.IPv6Address
    ) -> None:
        if addr in self._cloud_ips:
            raise ScopeViolation(
                f"Address {addr} is a cloud metadata endpoint and is permanently blocked."
            )

    def _check_excluded_ip(
        self, addr: ipaddress.IPv4Address | ipaddress.IPv6Address
    ) -> None:
        for excl in self._rules.excluded:
            try:
                excl_addr = ipaddress.ip_address(excl)
                if addr == excl_addr:
                    raise ScopeViolation(f"Address {addr} is explicitly excluded.")
            except ValueError:
                try:
                    excl_net = _parse_network(excl)
                    if addr in excl_net:
                        raise ScopeViolation(
                            f"Address {addr} is within excluded CIDR {excl_net}."
                        )
                except ValueError:
                    pass

    def _check_excluded_domain(self, domain: str) -> None:
        for excl in self._rules.excluded:
            if domain == excl or domain.endswith(f".{excl}"):
                raise ScopeViolation(f"Domain {domain!r} is explicitly excluded.")

    def _domain_explicitly_allowed(self, domain: str) -> bool:
        for allowed in self._rules.allowed_domains:
            if domain == allowed or domain.endswith(f".{allowed}"):
                return True
        return False
