"""Email ingestion endpoints for importing investigation data from emails."""
import secrets
from typing import Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.api.v1.auth.dependencies import get_current_user

log = structlog.get_logger()
router = APIRouter()


class EmailIngestRequest(BaseModel):
    subject: str = ""
    from_address: str = ""
    to_address: str = ""
    body_text: str = Field(..., min_length=1, max_length=100000)
    body_html: str = ""
    attachments: list[dict[str, str]] = []
    headers: dict[str, str] = {}
    auto_extract: bool = True


class EmailIngestResponse(BaseModel):
    ingestion_id: str
    extracted_entities: list[dict[str, str]]
    investigation_id: str | None
    status: str


class IngestConfigResponse(BaseModel):
    ingest_email: str
    enabled: bool
    auto_create_investigation: bool
    allowed_senders: list[str]


@router.post("/email-ingestion/ingest", response_model=EmailIngestResponse)
async def ingest_email(
    body: EmailIngestRequest, current_user: Any = Depends(get_current_user)
) -> EmailIngestResponse:
    """Ingest an email and extract OSINT-relevant entities."""
    entities: list[dict[str, str]] = []
    if body.auto_extract:
        import re

        emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", body.body_text)
        for email in set(emails):
            if email != body.from_address:
                entities.append({"value": email, "type": "email"})

        ips = re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", body.body_text)
        for ip in set(ips):
            entities.append({"value": ip, "type": "ip_address"})

        domains = re.findall(r"\b(?:[a-z0-9-]+\.)+[a-z]{2,}\b", body.body_text.lower())
        email_domains = {e.split("@")[1] for e in emails if "@" in e}
        for domain in set(domains):
            if domain not in email_domains:
                entities.append({"value": domain, "type": "domain"})

    return EmailIngestResponse(
        ingestion_id=secrets.token_hex(16),
        extracted_entities=entities,
        investigation_id=None,
        status="processed",
    )


@router.get("/email-ingestion/config", response_model=IngestConfigResponse)
async def get_ingest_config(
    current_user: Any = Depends(get_current_user),
) -> IngestConfigResponse:
    """Get email ingestion configuration."""
    return IngestConfigResponse(
        ingest_email="ingest@osint-platform.local",
        enabled=False,
        auto_create_investigation=False,
        allowed_senders=[],
    )
