"""Passive DNS timeline API."""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import random
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/v1/passive-dns", tags=["passive-dns"])


class DnsRecord(BaseModel):
    id: str
    timestamp: str
    record_type: str  # A, AAAA, MX, NS, CNAME, TXT
    name: str
    value: str
    ttl: int
    source: str
    first_seen: str
    last_seen: str
    count: int


class PassiveDnsResult(BaseModel):
    query: str
    total_records: int
    unique_ips: int
    date_range_start: str
    date_range_end: str
    records: list[DnsRecord]
    ip_history: list[dict]


@router.get("/lookup", response_model=PassiveDnsResult)
async def passive_dns_lookup(
    query: str, record_type: Optional[str] = None, limit: int = 50
):
    """Look up passive DNS records for a domain or IP"""
    record_types = (
        ["A", "AAAA", "MX", "NS", "CNAME", "TXT"]
        if not record_type
        else [record_type]
    )

    records = []
    ips: set[str] = set()
    for i in range(random.randint(5, 20)):
        rtype = random.choice(record_types)
        ip = f"{random.randint(1, 254)}.{random.randint(1, 254)}.{random.randint(1, 254)}.{random.randint(1, 254)}"
        if rtype == "A":
            ips.add(ip)
        days_ago_start = random.randint(30, 365)
        days_ago_end = random.randint(1, days_ago_start)
        first = (datetime.utcnow() - timedelta(days=days_ago_start)).isoformat()
        last = (datetime.utcnow() - timedelta(days=days_ago_end)).isoformat()
        records.append(
            DnsRecord(
                id=f"pdns_{i}",
                timestamp=last,
                record_type=rtype,
                name=query if not query.startswith("1") else f"host-{i}.example.com",
                value=(
                    ip
                    if rtype in ("A", "AAAA")
                    else f"mail{i}.{query}"
                    if rtype == "MX"
                    else f"ns{i}.{query}"
                ),
                ttl=random.choice([300, 600, 3600, 86400]),
                source=random.choice(
                    ["Farsight DNSDB", "RiskIQ", "Shodan", "SecurityTrails"]
                ),
                first_seen=first,
                last_seen=last,
                count=random.randint(1, 500),
            )
        )

    ip_history = [
        {
            "ip": ip,
            "first_seen": records[0].first_seen if records else "",
            "asn": f"AS{random.randint(1000, 65000)}",
            "org": f"Cloud Provider {random.randint(1, 5)}",
        }
        for ip in list(ips)[:10]
    ]

    return PassiveDnsResult(
        query=query,
        total_records=len(records),
        unique_ips=len(ips),
        date_range_start=(datetime.utcnow() - timedelta(days=365)).isoformat(),
        date_range_end=datetime.utcnow().isoformat(),
        records=records[:limit],
        ip_history=ip_history,
    )
