"""Investigation templates — pre-configured scan profiles for common OSINT use cases.

GET  /api/v1/investigation-templates — list available templates
POST /api/v1/investigation-templates/{template_id}/apply — create investigation from template
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.auth.dependencies import get_current_user
from src.adapters.db.database import get_db
from src.adapters.db.models import UserModel

log = structlog.get_logger(__name__)

router = APIRouter()

_TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "person_deep",
        "name": "Person Deep Dive",
        "description": "Comprehensive person OSINT: social media, breaches, court records, people-search, academic",
        "category": "Person OSINT",
        "icon": "User",
        "input_types": ["email", "username", "phone"],
        "scanners": [
            "email_breach", "hibp", "people_search", "court_records", "academic",
            "whois_history", "discord", "github", "twitter", "linkedin",
            "dating_app", "fediverse_deep", "gaming_platform",
        ],
        "estimated_time_seconds": 120,
        "tags": ["person", "identity", "social"],
    },
    {
        "id": "domain_recon",
        "name": "Domain Reconnaissance",
        "description": "Full domain intelligence: DNS, WHOIS, certificates, subdomains, tech stack, job intel",
        "category": "Domain OSINT",
        "icon": "Globe",
        "input_types": ["domain"],
        "scanners": [
            "dns_recon", "whois", "cert_transparency", "subdomain_enum",
            "http_fingerprint", "shodan_bulk", "job_intel", "brand_impersonation",
            "sec_edgar", "cloud_exposure", "subdomain_takeover",
        ],
        "estimated_time_seconds": 90,
        "tags": ["domain", "network", "corporate"],
    },
    {
        "id": "corporate_intel",
        "name": "Corporate Intelligence",
        "description": "Company research: SEC filings, job postings, LinkedIn, news, brand monitoring",
        "category": "Corporate OSINT",
        "icon": "Building",
        "input_types": ["domain", "email"],
        "scanners": [
            "sec_edgar", "job_intel", "linkedin", "news_media",
            "brand_impersonation", "whois_history", "github", "cloud_exposure",
        ],
        "estimated_time_seconds": 60,
        "tags": ["corporate", "business", "finance"],
    },
    {
        "id": "threat_actor",
        "name": "Threat Actor Profile",
        "description": "Threat intelligence: dark web mentions, crypto tracing, breach data, paste monitor",
        "category": "Threat Intelligence",
        "icon": "AlertTriangle",
        "input_types": ["username", "email", "domain"],
        "scanners": [
            "darkweb_forum", "paste_monitor", "crypto_clustering",
            "leaked_creds", "iban", "telegram_osint", "hibp",
            "darkweb_forum", "virustotal",
        ],
        "estimated_time_seconds": 180,
        "tags": ["threat", "darkweb", "crypto"],
    },
    {
        "id": "network_attack_surface",
        "name": "Network Attack Surface",
        "description": "Infrastructure exposure: open ports, CVEs, SSL, cloud services, DNS",
        "category": "Security Assessment",
        "icon": "Shield",
        "input_types": ["domain", "ip"],
        "scanners": [
            "shodan_bulk", "nmap", "ssl_scan", "cloud_exposure",
            "subdomain_takeover", "http_fingerprint", "cert_transparency",
        ],
        "estimated_time_seconds": 300,
        "tags": ["network", "security", "pentest"],
    },
    {
        "id": "crypto_investigation",
        "name": "Cryptocurrency Investigation",
        "description": "Blockchain analysis: wallet clustering, exchange identification, transaction history",
        "category": "Financial OSINT",
        "icon": "DollarSign",
        "input_types": ["username", "email"],
        "scanners": [
            "crypto_clustering", "iban", "darkweb_forum",
        ],
        "estimated_time_seconds": 60,
        "tags": ["crypto", "finance", "blockchain"],
    },
    {
        "id": "vehicle_check",
        "name": "Vehicle History Check",
        "description": "VIN decode, recall history, NHTSA complaints",
        "category": "Vehicle OSINT",
        "icon": "Car",
        "input_types": ["username"],
        "scanners": ["vin"],
        "estimated_time_seconds": 30,
        "tags": ["vehicle", "vin", "nhtsa"],
    },
    {
        "id": "social_media_audit",
        "name": "Social Media Audit",
        "description": "Cross-platform social presence: username search across 30+ platforms, Telegram, Discord, gaming",
        "category": "Social OSINT",
        "icon": "Users",
        "input_types": ["username", "email"],
        "scanners": [
            "username_scanner", "discord", "gaming_platform", "telegram_osint",
            "fediverse_deep", "dating_app", "skype", "whatsapp",
        ],
        "estimated_time_seconds": 90,
        "tags": ["social", "username", "identity"],
    },
]


class TemplateListResponse(BaseModel):
    templates: list[dict[str, Any]]
    total: int


@router.get("/investigation-templates", response_model=TemplateListResponse,
            tags=["investigation-templates"])
async def list_templates(
    category: str | None = None,
    current_user: UserModel = Depends(get_current_user),
) -> TemplateListResponse:
    """List all available investigation templates."""
    templates = _TEMPLATES
    if category:
        templates = [t for t in templates if t["category"].lower() == category.lower()]
    return TemplateListResponse(templates=templates, total=len(templates))


@router.get("/investigation-templates/{template_id}", tags=["investigation-templates"])
async def get_template(
    template_id: str,
    current_user: UserModel = Depends(get_current_user),
) -> dict[str, Any]:
    """Get a specific investigation template by ID."""
    template = next((t for t in _TEMPLATES if t["id"] == template_id), None)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Template '{template_id}' not found")
    return template
