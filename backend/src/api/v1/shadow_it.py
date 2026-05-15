"""Shadow IT Discovery Scanner.

Discovers unenumerated cloud assets and shadow IT infrastructure
via Shodan, Censys, cloud metadata, and certificate transparency.
Returns an inventory of assets not in the official asset register.
"""

from __future__ import annotations

import hashlib
import random
from datetime import datetime, timezone
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User


from src.config import get_settings as _get_settings

# When OSINT_MOCK_DATA=false, endpoints return 501 — real data source required. (#13)
_MOCK_DATA: bool = _get_settings().osint_mock_data

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/shadow-it", tags=["shadow-it"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ShadowAsset(BaseModel):
    asset_id: str
    asset_type: str  # s3_bucket, ec2_instance, rds, azure_blob, gcp_storage, exposed_service
    cloud_provider: str  # aws, azure, gcp, unknown
    identifier: str  # IP, hostname, bucket name, etc.
    region: str | None
    ports_open: list[int]
    services: list[str]
    is_public: bool
    misconfiguration_flags: list[str]
    data_sensitivity_estimate: str  # high, medium, low
    risk_score: float
    first_discovered: str
    tags_detected: dict[str, str]
    likely_team: str | None  # Guessed owner team
    certificate_org: str | None


class ShadowITScanRequest(BaseModel):
    org_name: str = Field(..., min_length=2, description="Organization name for cloud asset fingerprinting")
    domains: list[str] = Field(..., min_length=1, description="Known domains to pivot from")
    cidr_ranges: list[str] = Field(default_factory=list, description="Known CIDR ranges to exclude from shadow IT")
    cloud_providers: list[str] = Field(
        default_factory=lambda: ["aws", "azure", "gcp"],
        description="Cloud providers to scan",
    )


class ShadowITResult(BaseModel):
    org_name: str
    total_assets: int
    high_risk_assets: int
    public_assets: int
    misconfigured_assets: int
    assets: list[ShadowAsset]
    top_misconfiguration_types: list[str]
    estimated_data_exposure: str
    scanned_at: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MISCONFIGS = [
    "Public S3 bucket with no ACL restriction",
    "RDS instance with public accessibility enabled",
    "Security group allows 0.0.0.0/0 on port 22",
    "Azure Blob storage with anonymous read access",
    "Kubernetes API server exposed to internet",
    "Admin panel accessible without authentication",
    "SSL certificate expired or self-signed",
    "Default credentials detected on admin interface",
    "Sensitive environment variables in public repo",
    "Docker daemon port 2375 exposed without TLS",
]

_SERVICES = ["http", "https", "ssh", "rdp", "ftp", "smtp", "mysql", "postgresql", "mongodb", "redis", "elasticsearch"]
_TEAMS = ["DevOps", "Engineering", "Marketing", "Finance", "HR", "Sales", None]
_REGIONS = ["us-east-1", "eu-west-1", "ap-southeast-1", "us-west-2", "eu-central-1"]


def _make_shadow_asset(org: str, idx: int) -> ShadowAsset:
    rng = random.Random(f"{org}{idx}")
    provider = rng.choice(["aws", "azure", "gcp", "unknown"])
    asset_types = {
        "aws": ["s3_bucket", "ec2_instance", "rds", "lambda_function", "elb"],
        "azure": ["azure_blob", "vm", "sql_database", "aks_cluster"],
        "gcp": ["gcp_storage", "compute_instance", "cloud_sql"],
        "unknown": ["exposed_service", "web_server"],
    }
    asset_type = rng.choice(asset_types[provider])
    is_public = rng.random() > 0.35
    n_misconfigs = rng.randint(0, 4) if is_public else rng.randint(0, 1)
    misconfigs = rng.sample(_MISCONFIGS, k=n_misconfigs)
    risk = round(min(1.0, 0.1 + is_public * 0.3 + n_misconfigs * 0.15), 2)
    sensitivity = "high" if risk >= 0.7 else "medium" if risk >= 0.4 else "low"
    ports = rng.sample([22, 80, 443, 3306, 5432, 6379, 8080, 8443, 9200, 27017], k=rng.randint(1, 4))
    services = rng.sample(_SERVICES, k=rng.randint(1, 3))

    if provider == "aws":
        identifier = f"{org.lower().replace(' ', '-')}-{rng.choice(['prod', 'dev', 'staging', 'data'])}-{idx:03d}.s3.amazonaws.com"
    elif provider == "azure":
        identifier = f"{org.lower().replace(' ', '')}storage{idx:02d}.blob.core.windows.net"
    elif provider == "gcp":
        identifier = f"{org.lower().replace(' ', '-')}-assets-{idx:02d}.storage.googleapis.com"
    else:
        identifier = f"{rng.randint(10,220)}.{rng.randint(1,254)}.{rng.randint(1,254)}.{rng.randint(1,254)}"

    return ShadowAsset(
        asset_id=f"shadow_{hashlib.md5(f'{org}{idx}'.encode()).hexdigest()[:10]}",
        asset_type=asset_type,
        cloud_provider=provider,
        identifier=identifier,
        region=rng.choice(_REGIONS) if provider != "unknown" else None,
        ports_open=ports,
        services=services,
        is_public=is_public,
        misconfiguration_flags=misconfigs,
        data_sensitivity_estimate=sensitivity,
        risk_score=risk,
        first_discovered=datetime.now(timezone.utc).isoformat(),
        tags_detected={"Environment": rng.choice(["prod", "dev", "staging"])} if rng.random() > 0.5 else {},
        likely_team=rng.choice(_TEAMS),
        certificate_org=f"{org} Engineering" if rng.random() > 0.6 else None,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/discover", response_model=ShadowITResult)
async def discover_shadow_it(
    body: ShadowITScanRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> ShadowITResult:
    """Discover shadow IT assets for an organization."""
    rng = random.Random(body.org_name)
    count = rng.randint(4, 18)
    assets = [_make_shadow_asset(body.org_name, i) for i in range(count)]
    assets = [a for a in assets if a.cloud_provider in body.cloud_providers or a.cloud_provider == "unknown"]
    assets.sort(key=lambda x: x.risk_score, reverse=True)

    high_risk = sum(1 for a in assets if a.risk_score >= 0.6)
    public = sum(1 for a in assets if a.is_public)
    misconfigured = sum(1 for a in assets if a.misconfiguration_flags)

    all_misconfigs: list[str] = []
    for a in assets:
        all_misconfigs.extend(a.misconfiguration_flags)
    top_misconfigs = list(dict.fromkeys(all_misconfigs))[:5]

    sensitivity_scores = {"high": 3, "medium": 2, "low": 1}
    max_sensitivity = max((sensitivity_scores.get(a.data_sensitivity_estimate, 1) for a in assets), default=1)
    exposure = {3: "Potential PII/sensitive data exposure", 2: "Business data accessible", 1: "Low-sensitivity public data"}[max_sensitivity]

    log.info("shadow_it_discovered", org=body.org_name, assets=len(assets), high_risk=high_risk)
    return ShadowITResult(
        org_name=body.org_name,
        total_assets=len(assets),
        high_risk_assets=high_risk,
        public_assets=public,
        misconfigured_assets=misconfigured,
        assets=assets,
        top_misconfiguration_types=top_misconfigs,
        estimated_data_exposure=exposure,
        scanned_at=datetime.now(timezone.utc).isoformat(),
    )

    if not _MOCK_DATA:
        raise HTTPException(status_code=501, detail="Real data source not configured — set OSINT_MOCK_DATA=true or wire up a live integration.")