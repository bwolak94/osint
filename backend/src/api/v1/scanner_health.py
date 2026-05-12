"""Scanner registry health endpoint — reports which scanners are available based on configured API keys."""

import os
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User

router = APIRouter(prefix="/scanners/health", tags=["scanners"])

# Map scanner names to their required environment variable and category
SCANNER_API_KEYS: dict[str, tuple[str, str]] = {
    "shodan": ("SHODAN_API_KEY", "Infrastructure"),
    "virustotal": ("VIRUSTOTAL_API_KEY", "Threat Intel"),
    "hibp": ("HIBP_API_KEY", "Breach Intel"),
    "greynoise": ("GREYNOISE_API_KEY", "Threat Intel"),
    "otx": ("OTX_API_KEY", "Threat Intel"),
    "github": ("GITHUB_TOKEN", "Social"),
    "twitter": ("TWITTER_BEARER_TOKEN", "Social"),
    "hunter": ("HUNTER_API_KEY", "Email"),
    "urlscan": ("URLSCAN_API_KEY", "Web"),
    "threatfox": ("THREATFOX_API_KEY", "Threat Intel"),
    "bevigil": ("BEVIGIL_API_KEY", "Mobile"),
    "wigle": ("WIGLE_API_KEY", "Geolocation"),
}

BUILT_IN_SCANNERS: list[tuple[str, str]] = [
    ("dns", "Infrastructure"),
    ("whois", "Infrastructure"),
    ("asn", "Infrastructure"),
    ("geoip", "Infrastructure"),
    ("cert", "Infrastructure"),
    ("subdomain", "Infrastructure"),
    ("holehe", "Identity"),
    ("sherlock", "Identity"),
    ("maigret", "Identity"),
    ("breach", "Breach Intel"),
    ("email_header", "Email"),
    ("metadata", "File"),
    ("wayback", "Web"),
    ("paste", "Web"),
]


class ScannerStatus(BaseModel):
    name: str
    enabled: bool
    reason: str
    category: str


@router.get("", response_model=list[ScannerStatus])
async def get_scanner_health(
    _: Annotated[User, Depends(get_current_user)],
) -> list[ScannerStatus]:
    """Return availability status for all registered scanners."""
    results: list[ScannerStatus] = []

    for name, (env_var, category) in SCANNER_API_KEYS.items():
        enabled = bool(os.environ.get(env_var))
        results.append(
            ScannerStatus(
                name=name,
                enabled=enabled,
                reason=f"API key configured ({env_var})" if enabled else f"No API key ({env_var} not set)",
                category=category,
            )
        )

    for name, category in BUILT_IN_SCANNERS:
        results.append(
            ScannerStatus(
                name=name,
                enabled=True,
                reason="Built-in (no key needed)",
                category=category,
            )
        )

    return sorted(results, key=lambda s: (not s.enabled, s.category, s.name))
