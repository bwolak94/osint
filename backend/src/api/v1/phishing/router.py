"""Internal phishing simulation endpoints — Redis-backed state."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.auth.dependencies import get_current_user, get_redis
from src.config import get_settings
from src.core.domain.entities.user import User
from src.dependencies import get_db

log = structlog.get_logger(__name__)
router = APIRouter(tags=["phishing"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
UserDep = Annotated[User, Depends(get_current_user)]
RedisDep = Annotated[Redis, Depends(get_redis)]

PhishingTemplate = Literal["office365", "vpn", "custom"]

# Redis key TTL — 30 days (seconds)
_CAMPAIGN_TTL = 60 * 60 * 24 * 30
_REDIS_CAMPAIGN_PREFIX = "phishing:campaign:"
_REDIS_RECIPIENT_PREFIX = "phishing:recipient:"

# ---------------------------------------------------------------------------
# HTML Templates
# ---------------------------------------------------------------------------

_TEMPLATES: dict[str, str] = {
    "office365": """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Sign in to your account</title>
<style>body{font-family:'Segoe UI',sans-serif;background:#f3f2f1;display:flex;justify-content:center;align-items:center;height:100vh;margin:0}
.box{background:#fff;padding:44px;width:440px;box-shadow:0 2px 4px rgba(0,0,0,.1)}
input{width:100%;box-sizing:border-box;border:1px solid #8a8886;padding:6px 10px;margin-top:4px;font-size:15px}
button{background:#0078d4;color:#fff;border:none;width:100%;padding:8px;font-size:15px;cursor:pointer;margin-top:16px}
</style></head><body><div class="box">
<img src="https://img-prod-cms-rt-microsoft-com.akamaized.net/cms/api/am/imageFileData/RE1Mu3b" width="108" alt="Microsoft">
<h2 style="font-weight:300;font-size:1.5em">Sign in</h2>
<input type="email" placeholder="Email, phone, or Skype">
<a href="#" style="display:block;margin-top:8px;font-size:.85em">No account? Create one!</a>
<input type="password" placeholder="Password" style="margin-top:16px">
<button type="button">Sign in</button>
</div></body></html>""",
    "vpn": """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Corporate VPN Login</title>
<style>body{font-family:Arial,sans-serif;background:#1a1a2e;display:flex;justify-content:center;align-items:center;height:100vh;margin:0}
.box{background:#16213e;color:#eee;padding:44px;width:380px;border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,.5)}
h2{text-align:center;color:#0f3460;color:#e94560;margin-bottom:24px}
label{font-size:.85em;color:#aaa}
input{width:100%;box-sizing:border-box;background:#0f3460;border:1px solid #e94560;color:#fff;padding:8px 12px;margin-top:4px;border-radius:4px;font-size:14px}
button{background:#e94560;color:#fff;border:none;width:100%;padding:10px;font-size:15px;cursor:pointer;border-radius:4px;margin-top:20px}
</style></head><body><div class="box">
<h2>Corporate VPN Portal</h2>
<label>Username</label><input type="text" placeholder="username@corp.com">
<label style="margin-top:12px;display:block">Password</label><input type="password" placeholder="••••••••">
<button type="button">Connect</button>
</div></body></html>""",
    "custom": """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Login</title>
<style>body{font-family:sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;background:#f0f0f0}
.box{background:#fff;padding:40px;border-radius:6px;width:360px;box-shadow:0 2px 8px rgba(0,0,0,.15)}
input{width:100%;box-sizing:border-box;border:1px solid #ccc;padding:8px;margin-top:6px;border-radius:4px}
button{background:#333;color:#fff;border:none;width:100%;padding:10px;cursor:pointer;border-radius:4px;margin-top:16px}
</style></head><body><div class="box">
<h2>Login</h2>
<label>Email<input type="email" placeholder="you@example.com"></label>
<label style="margin-top:12px;display:block">Password<input type="password" placeholder="••••••••"></label>
<button type="button">Log in</button>
</div></body></html>""",
}

# 1×1 transparent PNG bytes
_TRANSPARENT_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _recipient_hash(campaign_id: str, email: str) -> str:
    return hashlib.sha256(f"{campaign_id}:{email}".encode()).hexdigest()[:16]


def _campaign_key(campaign_id: str) -> str:
    return f"{_REDIS_CAMPAIGN_PREFIX}{campaign_id}"


def _recipient_key(campaign_id: str, recipient_hash: str) -> str:
    return f"{_REDIS_RECIPIENT_PREFIX}{campaign_id}:{recipient_hash}"


async def _get_campaign_or_404(campaign_id: str, redis: Redis) -> dict[str, Any]:
    raw = await redis.get(_campaign_key(campaign_id))
    if raw is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")
    return json.loads(raw)


async def _save_campaign(campaign_id: str, data: dict[str, Any], redis: Redis) -> None:
    await redis.setex(_campaign_key(campaign_id), _CAMPAIGN_TTL, json.dumps(data, default=str))


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CreateCampaignRequest(BaseModel):
    name: str
    engagement_id: uuid.UUID
    template: PhishingTemplate = "office365"
    target_emails: list[str]


class CampaignResponse(BaseModel):
    id: str
    name: str
    engagement_id: str
    template: str
    status: str
    target_emails: list[str]
    created_at: str
    stats: dict[str, int]


class LaunchCampaignResponse(BaseModel):
    campaign_id: str
    status: str
    recipients: list[dict[str, str]]
    tracking_urls: dict[str, str]


# ---------------------------------------------------------------------------
# POST /phishing/campaigns
# ---------------------------------------------------------------------------


@router.post(
    "/phishing/campaigns",
    response_model=CampaignResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_campaign(
    request: CreateCampaignRequest,
    current_user: UserDep,
    redis: RedisDep,
) -> CampaignResponse:
    """Create a new phishing simulation campaign."""
    campaign_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    data: dict[str, Any] = {
        "id": campaign_id,
        "name": request.name,
        "engagement_id": str(request.engagement_id),
        "template": request.template,
        "status": "draft",
        "target_emails": request.target_emails,
        "created_at": now,
        "stats": {"sent": 0, "opened": 0, "clicked": 0, "submitted": 0},
        "recipients": {},
    }

    await _save_campaign(campaign_id, data, redis)

    log.info("phishing_campaign_created", campaign_id=campaign_id, name=request.name)
    return CampaignResponse(**{k: v for k, v in data.items() if k != "recipients"})


# ---------------------------------------------------------------------------
# GET /phishing/campaigns
# ---------------------------------------------------------------------------


@router.get("/phishing/campaigns", response_model=list[CampaignResponse])
async def list_campaigns(
    current_user: UserDep,
    redis: RedisDep,
) -> list[CampaignResponse]:
    """List all phishing campaigns stored in Redis."""
    pattern = f"{_REDIS_CAMPAIGN_PREFIX}*"
    keys: list[bytes] = []
    async for key in redis.scan_iter(pattern):
        keys.append(key)

    campaigns: list[CampaignResponse] = []
    for key in keys:
        raw = await redis.get(key)
        if raw:
            data = json.loads(raw)
            campaigns.append(
                CampaignResponse(**{k: v for k, v in data.items() if k != "recipients"})
            )

    campaigns.sort(key=lambda c: c.created_at, reverse=True)
    return campaigns


# ---------------------------------------------------------------------------
# GET /phishing/campaigns/{id}
# ---------------------------------------------------------------------------


@router.get("/phishing/campaigns/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: str,
    current_user: UserDep,
    redis: RedisDep,
) -> CampaignResponse:
    """Get campaign details including sent/opened/clicked/submitted stats."""
    data = await _get_campaign_or_404(campaign_id, redis)
    return CampaignResponse(**{k: v for k, v in data.items() if k != "recipients"})


# ---------------------------------------------------------------------------
# POST /phishing/campaigns/{id}/launch
# ---------------------------------------------------------------------------


@router.post(
    "/phishing/campaigns/{campaign_id}/launch",
    response_model=LaunchCampaignResponse,
)
async def launch_campaign(
    campaign_id: str,
    current_user: UserDep,
    redis: RedisDep,
) -> LaunchCampaignResponse:
    """
    Launch a phishing campaign.

    Generates a unique tracking hash per recipient and stores it in Redis.
    Does not send actual emails unless SMTP is configured.
    """
    settings = get_settings()
    data = await _get_campaign_or_404(campaign_id, redis)

    if data["status"] == "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Campaign is already active.",
        )

    recipients_info: list[dict[str, str]] = []
    recipients_map: dict[str, str] = {}

    base_url = settings.base_url.rstrip("/")

    for email in data["target_emails"]:
        rhash = _recipient_hash(campaign_id, email)
        recipients_map[rhash] = email

        # Store recipient state in Redis
        recipient_state = {
            "email": email,
            "hash": rhash,
            "sent": True,
            "opened": False,
            "clicked": False,
            "submitted": False,
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }
        await redis.setex(
            _recipient_key(campaign_id, rhash),
            _CAMPAIGN_TTL,
            json.dumps(recipient_state),
        )

        open_url = f"{base_url}/phishing/track/open/{campaign_id}/{rhash}"
        submit_url = f"{base_url}/phishing/track/submit/{campaign_id}/{rhash}"
        recipients_info.append(
            {
                "email": email,
                "hash": rhash,
                "open_tracking_url": open_url,
                "submit_tracking_url": submit_url,
            }
        )

    data["status"] = "active"
    data["stats"]["sent"] = len(data["target_emails"])
    data["recipients"] = recipients_map
    data["launched_at"] = datetime.now(timezone.utc).isoformat()

    await _save_campaign(campaign_id, data, redis)

    template_html = _TEMPLATES.get(data["template"], _TEMPLATES["custom"])

    log.info("phishing_campaign_launched", campaign_id=campaign_id, recipients=len(recipients_info))
    return LaunchCampaignResponse(
        campaign_id=campaign_id,
        status="active",
        recipients=recipients_info,
        tracking_urls={
            "open_pixel": f"{base_url}/phishing/track/open/{campaign_id}/{{hash}}",
            "submit": f"{base_url}/phishing/track/submit/{campaign_id}/{{hash}}",
            "phishing_page": f"{base_url}/phishing/page/{campaign_id}",
        },
    )


# ---------------------------------------------------------------------------
# POST /phishing/track/open/{campaign_id}/{recipient_hash}
# Tracking pixel — returns 1×1 transparent PNG
# ---------------------------------------------------------------------------


@router.post(
    "/phishing/track/open/{campaign_id}/{recipient_hash}",
    response_class=Response,
    include_in_schema=False,
)
@router.get(
    "/phishing/track/open/{campaign_id}/{recipient_hash}",
    response_class=Response,
    include_in_schema=False,
)
async def track_open(
    campaign_id: str,
    recipient_hash: str,
    redis: RedisDep,
) -> Response:
    """Tracking pixel endpoint — marks email as opened."""
    key = _recipient_key(campaign_id, recipient_hash)
    raw = await redis.get(key)
    if raw:
        state: dict[str, Any] = json.loads(raw)
        if not state.get("opened"):
            state["opened"] = True
            state["opened_at"] = datetime.now(timezone.utc).isoformat()
            await redis.setex(key, _CAMPAIGN_TTL, json.dumps(state))

            # Increment campaign stat
            campaign_raw = await redis.get(_campaign_key(campaign_id))
            if campaign_raw:
                campaign_data = json.loads(campaign_raw)
                campaign_data["stats"]["opened"] = campaign_data["stats"].get("opened", 0) + 1
                await _save_campaign(campaign_id, campaign_data, redis)

    return Response(content=_TRANSPARENT_PNG, media_type="image/png")


# ---------------------------------------------------------------------------
# POST /phishing/track/submit/{campaign_id}/{recipient_hash}
# Credential submission tracking
# ---------------------------------------------------------------------------


@router.post(
    "/phishing/track/submit/{campaign_id}/{recipient_hash}",
    status_code=status.HTTP_204_NO_CONTENT, response_model=None,
    
)
async def track_submit(
    campaign_id: str,
    recipient_hash: str,
    redis: RedisDep,
) -> None:
    """Track a credential submission from a phishing landing page."""
    key = _recipient_key(campaign_id, recipient_hash)
    raw = await redis.get(key)
    if raw:
        state: dict[str, Any] = json.loads(raw)
        updated = False
        if not state.get("clicked"):
            state["clicked"] = True
            state["clicked_at"] = datetime.now(timezone.utc).isoformat()
            updated = True
        if not state.get("submitted"):
            state["submitted"] = True
            state["submitted_at"] = datetime.now(timezone.utc).isoformat()
            updated = True

        if updated:
            await redis.setex(key, _CAMPAIGN_TTL, json.dumps(state))

            campaign_raw = await redis.get(_campaign_key(campaign_id))
            if campaign_raw:
                campaign_data = json.loads(campaign_raw)
                if state.get("clicked"):
                    campaign_data["stats"]["clicked"] = campaign_data["stats"].get("clicked", 0) + 1
                if state.get("submitted"):
                    campaign_data["stats"]["submitted"] = (
                        campaign_data["stats"].get("submitted", 0) + 1
                    )
                await _save_campaign(campaign_id, campaign_data, redis)

        log.info(
            "phishing_submission_tracked",
            campaign_id=campaign_id,
            recipient_hash=recipient_hash,
        )


# ---------------------------------------------------------------------------
# GET /phishing/templates — return available HTML templates
# ---------------------------------------------------------------------------


@router.get("/phishing/templates", response_model=dict[str, str])
async def list_templates(current_user: UserDep) -> dict[str, str]:
    """Return available phishing page templates as HTML strings."""
    return _TEMPLATES
