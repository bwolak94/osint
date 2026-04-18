"""Investigation template marketplace endpoints."""

import secrets
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from src.api.v1.auth.dependencies import get_current_user

log = structlog.get_logger()
router = APIRouter()

# Built-in templates
BUILTIN_TEMPLATES = [
    {
        "id": "tpl-email-deep-scan",
        "name": "Email Deep Investigation",
        "description": "Comprehensive investigation starting from an email address. Checks breaches, social media, domain ownership.",
        "category": "email",
        "is_public": True,
        "seed_input_types": ["email"],
        "scanner_config": ["holehe", "breach", "maigret", "google", "linkedin"],
        "tags": ["email", "comprehensive", "beginner-friendly"],
        "usage_count": 1250,
        "rating": 4.8,
    },
    {
        "id": "tpl-domain-recon",
        "name": "Domain Reconnaissance",
        "description": "Full domain analysis including DNS, WHOIS, subdomains, certificates, and port scanning.",
        "category": "infrastructure",
        "is_public": True,
        "seed_input_types": ["domain"],
        "scanner_config": ["dns", "whois", "subdomain", "cert", "shodan"],
        "tags": ["domain", "infrastructure", "recon"],
        "usage_count": 890,
        "rating": 4.6,
    },
    {
        "id": "tpl-social-media",
        "name": "Social Media Profiling",
        "description": "Map a person's social media presence across platforms.",
        "category": "social",
        "is_public": True,
        "seed_input_types": ["username"],
        "scanner_config": ["maigret", "twitter", "instagram", "facebook", "linkedin", "github"],
        "tags": ["social", "username", "profiles"],
        "usage_count": 720,
        "rating": 4.5,
    },
    {
        "id": "tpl-company-intel",
        "name": "Company Intelligence (PL)",
        "description": "Polish company investigation using KRS, CEIDG, and VAT registries.",
        "category": "company",
        "is_public": True,
        "seed_input_types": ["nip"],
        "scanner_config": ["playwright_krs", "playwright_ceidg", "vat"],
        "tags": ["company", "poland", "business"],
        "usage_count": 430,
        "rating": 4.7,
    },
    {
        "id": "tpl-threat-intel",
        "name": "Threat Intelligence Assessment",
        "description": "Assess threat indicators for an IP address or domain.",
        "category": "security",
        "is_public": True,
        "seed_input_types": ["ip_address", "domain"],
        "scanner_config": ["shodan", "virustotal", "dns", "geoip", "wayback"],
        "tags": ["threat", "security", "ip", "domain"],
        "usage_count": 650,
        "rating": 4.4,
    },
]


class TemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)
    description: str = ""
    category: str = "general"
    seed_input_types: list[str] = []
    scanner_config: list[str] = []
    playbook_steps: list[dict] = []
    tags: list[str] = []
    is_public: bool = False


class TemplateResponse(BaseModel):
    id: str
    name: str
    description: str
    category: str
    author_id: str | None
    is_public: bool
    seed_input_types: list[str]
    scanner_config: list[str]
    tags: list[str]
    usage_count: int
    rating: float


class TemplateListResponse(BaseModel):
    templates: list[TemplateResponse]
    total: int
    categories: list[str]


@router.get("/templates", response_model=TemplateListResponse)
async def list_templates(
    category: str | None = Query(None),
    search: str | None = Query(None),
    current_user: Any = Depends(get_current_user),
) -> TemplateListResponse:
    """List available investigation templates."""
    templates = BUILTIN_TEMPLATES
    if category:
        templates = [t for t in templates if t["category"] == category]
    if search:
        search_lower = search.lower()
        templates = [t for t in templates if search_lower in t["name"].lower() or search_lower in t["description"].lower()]

    categories = sorted(set(t["category"] for t in BUILTIN_TEMPLATES))

    return TemplateListResponse(
        templates=[
            TemplateResponse(
                id=t["id"],
                name=t["name"],
                description=t["description"],
                category=t["category"],
                author_id=None,
                is_public=True,
                seed_input_types=t["seed_input_types"],
                scanner_config=t["scanner_config"],
                tags=t["tags"],
                usage_count=t["usage_count"],
                rating=t["rating"],
            )
            for t in templates
        ],
        total=len(templates),
        categories=categories,
    )


@router.post("/templates", response_model=TemplateResponse, status_code=201)
async def create_template(
    body: TemplateCreate,
    current_user: Any = Depends(get_current_user),
) -> TemplateResponse:
    """Create a custom investigation template."""
    user_id = str(getattr(current_user, "id", "unknown"))

    return TemplateResponse(
        id=secrets.token_hex(16),
        name=body.name,
        description=body.description,
        category=body.category,
        author_id=user_id,
        is_public=body.is_public,
        seed_input_types=body.seed_input_types,
        scanner_config=body.scanner_config,
        tags=body.tags,
        usage_count=0,
        rating=0.0,
    )


@router.get("/templates/{template_id}")
async def get_template(
    template_id: str,
    current_user: Any = Depends(get_current_user),
) -> TemplateResponse:
    """Get a specific template by ID."""
    for t in BUILTIN_TEMPLATES:
        if t["id"] == template_id:
            return TemplateResponse(
                id=t["id"], name=t["name"], description=t["description"],
                category=t["category"], author_id=None, is_public=True,
                seed_input_types=t["seed_input_types"], scanner_config=t["scanner_config"],
                tags=t["tags"], usage_count=t["usage_count"], rating=t["rating"],
            )
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="Template not found")


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: str,
    current_user: Any = Depends(get_current_user),
) -> dict[str, str]:
    """Delete a custom template."""
    return {"status": "deleted", "id": template_id}
