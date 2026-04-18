"""IOC (Indicator of Compromise) feed export endpoints."""

from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from src.api.v1.auth.dependencies import get_current_user

log = structlog.get_logger()
router = APIRouter()


class IOCEntry(BaseModel):
    type: str  # ip, domain, url, email, hash
    value: str
    confidence: float
    source_scanner: str
    investigation_id: str
    first_seen: str
    last_seen: str
    tags: list[str]
    tlp: str  # white, green, amber, red


class IOCFeedResponse(BaseModel):
    iocs: list[IOCEntry]
    total: int
    generated_at: str
    format: str


SAMPLE_IOCS = [
    IOCEntry(
        type="ip", value="192.168.1.100", confidence=0.85,
        source_scanner="shodan", investigation_id="sample",
        first_seen="2026-01-01T00:00:00Z", last_seen="2026-04-17T00:00:00Z",
        tags=["suspicious", "port-scan"], tlp="amber",
    ),
    IOCEntry(
        type="domain", value="malicious-example.com", confidence=0.92,
        source_scanner="virustotal", investigation_id="sample",
        first_seen="2026-02-15T00:00:00Z", last_seen="2026-04-17T00:00:00Z",
        tags=["malware", "c2"], tlp="red",
    ),
]


@router.get("/ioc-feed", response_model=IOCFeedResponse)
async def get_ioc_feed(
    format: str = Query("json", pattern="^(json|stix|csv|misp)$"),
    tlp: str | None = Query(None, pattern="^(white|green|amber|red)$"),
    ioc_type: str | None = Query(None),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    current_user: Any = Depends(get_current_user),
) -> IOCFeedResponse:
    """Export IOCs as a feed in various formats."""
    iocs = SAMPLE_IOCS
    if tlp:
        iocs = [i for i in iocs if i.tlp == tlp]
    if ioc_type:
        iocs = [i for i in iocs if i.type == ioc_type]
    iocs = [i for i in iocs if i.confidence >= min_confidence]

    return IOCFeedResponse(
        iocs=iocs,
        total=len(iocs),
        generated_at=datetime.now(timezone.utc).isoformat(),
        format=format,
    )


@router.get("/ioc-feed/stix")
async def get_ioc_stix_bundle(
    current_user: Any = Depends(get_current_user),
) -> dict[str, Any]:
    """Export IOCs as a STIX 2.1 bundle."""
    now = datetime.now(timezone.utc).isoformat()
    objects = []
    for ioc in SAMPLE_IOCS:
        stix_type = {
            "ip": "ipv4-addr", "domain": "domain-name",
            "url": "url", "email": "email-addr",
        }.get(ioc.type, "artifact")

        objects.append({
            "type": "indicator",
            "spec_version": "2.1",
            "id": f"indicator--{ioc.value.replace('.', '-')}",
            "created": ioc.first_seen,
            "modified": ioc.last_seen,
            "name": f"{ioc.type}: {ioc.value}",
            "pattern": f"[{stix_type}:value = '{ioc.value}']",
            "pattern_type": "stix",
            "valid_from": ioc.first_seen,
            "confidence": int(ioc.confidence * 100),
            "labels": ioc.tags,
        })

    return {
        "type": "bundle",
        "id": "bundle--osint-ioc-feed",
        "spec_version": "2.1",
        "created": now,
        "objects": objects,
    }
