from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel


class AsnIntelRequest(BaseModel):
    query: str  # ASN number (e.g. "15169" or "AS15169") or IP address


class AsnPrefixSchema(BaseModel):
    prefix: str
    name: str | None = None
    description: str | None = None
    country: str | None = None


class AsnPeerSchema(BaseModel):
    asn: int
    name: str | None = None
    description: str | None = None
    country: str | None = None


class AsnIntelResponse(BaseModel):
    id: uuid.UUID | None = None
    created_at: datetime | None = None
    query: str
    found: bool
    asn: int | None = None
    name: str | None = None
    description: str | None = None
    country: str | None = None
    website: str | None = None
    email_contacts: list[str] = []
    abuse_contacts: list[str] = []
    rir: str | None = None
    prefixes_v4: list[AsnPrefixSchema] = []
    prefixes_v6: list[AsnPrefixSchema] = []
    peers: list[AsnPeerSchema] = []
    upstreams: list[AsnPeerSchema] = []
    downstreams: list[AsnPeerSchema] = []


class AsnIntelListResponse(BaseModel):
    items: list[AsnIntelResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
