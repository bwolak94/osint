"""ASN & BGP intelligence via BGPView API — free, no key required."""
from __future__ import annotations
from dataclasses import dataclass, field
import httpx

_BASE = "https://api.bgpview.io"


@dataclass
class AsnPrefix:
    prefix: str
    name: str | None = None
    description: str | None = None
    country: str | None = None


@dataclass
class AsnPeer:
    asn: int
    name: str | None = None
    description: str | None = None
    country: str | None = None


@dataclass
class AsnInfo:
    asn: int | None = None
    name: str | None = None
    description: str | None = None
    country: str | None = None
    website: str | None = None
    email_contacts: list[str] = field(default_factory=list)
    abuse_contacts: list[str] = field(default_factory=list)
    rir: str | None = None
    prefixes_v4: list[AsnPrefix] = field(default_factory=list)
    prefixes_v6: list[AsnPrefix] = field(default_factory=list)
    peers: list[AsnPeer] = field(default_factory=list)
    upstreams: list[AsnPeer] = field(default_factory=list)
    downstreams: list[AsnPeer] = field(default_factory=list)
    source: str = "bgpview"


async def lookup_asn(query: str) -> AsnInfo | None:
    """Look up an ASN number or IP address."""
    query = query.strip().upper().lstrip("AS")
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            # Detect if it's an IP address or ASN
            if any(c.isalpha() for c in query.replace(".", "").replace(":", "")):
                return None
            if "." in query or ":" in query:
                # IP lookup → get ASN first
                r = await client.get(f"{_BASE}/ip/{query}")
                if r.status_code != 200:
                    return None
                ip_data = r.json().get("data", {})
                prefixes = ip_data.get("prefixes", [])
                if not prefixes:
                    return None
                asn_num = prefixes[0].get("asn", {}).get("asn")
                if not asn_num:
                    return None
            else:
                asn_num = int(query)

            # ASN details
            r = await client.get(f"{_BASE}/asn/{asn_num}")
            if r.status_code != 200:
                return None
            d = r.json().get("data", {})

            # Prefixes
            rp = await client.get(f"{_BASE}/asn/{asn_num}/prefixes")
            prefixes_data = rp.json().get("data", {}) if rp.status_code == 200 else {}

            # Peers
            rpr = await client.get(f"{_BASE}/asn/{asn_num}/peers")
            peers_data = rpr.json().get("data", {}) if rpr.status_code == 200 else {}

            # Upstreams
            ru = await client.get(f"{_BASE}/asn/{asn_num}/upstreams")
            up_data = ru.json().get("data", {}) if ru.status_code == 200 else {}

            def _make_peers(items: list) -> list[AsnPeer]:
                return [
                    AsnPeer(
                        asn=p.get("asn", 0),
                        name=p.get("name"),
                        description=p.get("description"),
                        country=p.get("country_code"),
                    )
                    for p in (items or [])[:20]
                ]

            def _make_prefixes(items: list) -> list[AsnPrefix]:
                return [
                    AsnPrefix(
                        prefix=p.get("prefix", ""),
                        name=p.get("name"),
                        description=p.get("description"),
                        country=p.get("country_code"),
                    )
                    for p in (items or [])[:30]
                ]

            return AsnInfo(
                asn=d.get("asn"),
                name=d.get("name"),
                description=d.get("description"),
                country=d.get("country_code"),
                website=d.get("website"),
                email_contacts=d.get("email_contacts") or [],
                abuse_contacts=d.get("abuse_contacts") or [],
                rir=d.get("rir_allocation", {}).get("rir_name"),
                prefixes_v4=_make_prefixes(prefixes_data.get("ipv4_prefixes")),
                prefixes_v6=_make_prefixes(prefixes_data.get("ipv6_prefixes")),
                peers=_make_peers(peers_data.get("ipv4_peers")),
                upstreams=_make_peers(up_data.get("ipv4_upstreams")),
                downstreams=_make_peers(up_data.get("ipv4_downstreams")),
            )
        except Exception:
            return None
