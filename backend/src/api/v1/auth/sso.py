"""SSO / OIDC integration endpoints.

Supports:
  - OIDC Authorization Code flow (generic: works with Okta, Auth0, Azure AD, Keycloak)
  - SAML 2.0 SP-initiated flow (stub — requires python3-saml in production)

Configuration via environment variables:
  OIDC_CLIENT_ID, OIDC_CLIENT_SECRET, OIDC_ISSUER_URL
  OIDC_REDIRECT_URI (default: http://localhost:5173/sso/callback)
  SSO_ENABLED (default: false)
"""

from __future__ import annotations

import os
import secrets
import hashlib
import base64
import json
from datetime import datetime, timezone, timedelta
from typing import Annotated, Any
from urllib.parse import urlencode

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

import time
from jose import jwt as jose_jwt

from src.adapters.db.models import UserModel
from src.dependencies import get_db

_JWT_SECRET = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
_JWT_ALG = "HS256"
_JWT_TTL = 60 * 60  # 1 hour


def create_access_token(data: dict[str, str]) -> str:
    now = int(time.time())
    return jose_jwt.encode({**data, "iat": now, "exp": now + _JWT_TTL}, _JWT_SECRET, algorithm=_JWT_ALG)

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/auth/sso", tags=["sso"])

SSO_ENABLED = os.getenv("SSO_ENABLED", "false").lower() == "true"
OIDC_ISSUER_URL = os.getenv("OIDC_ISSUER_URL", "")
OIDC_CLIENT_ID = os.getenv("OIDC_CLIENT_ID", "")
OIDC_CLIENT_SECRET = os.getenv("OIDC_CLIENT_SECRET", "")
OIDC_REDIRECT_URI = os.getenv("OIDC_REDIRECT_URI", "http://localhost:5173/sso/callback")
OIDC_SCOPES = os.getenv("OIDC_SCOPES", "openid email profile")

DbDep = Annotated[AsyncSession, Depends(get_db)]

# In-memory PKCE state store (replace with Redis for multi-instance)
_state_store: dict[str, dict[str, str]] = {}


def _require_sso() -> None:
    if not SSO_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SSO is not enabled. Set SSO_ENABLED=true in environment.",
        )


# ---------------------------------------------------------------------------
# PKCE helpers
# ---------------------------------------------------------------------------

def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


# ---------------------------------------------------------------------------
# OIDC discovery
# ---------------------------------------------------------------------------

async def _discover_oidc() -> dict[str, Any]:
    discovery_url = f"{OIDC_ISSUER_URL.rstrip('/')}/.well-known/openid-configuration"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(discovery_url)
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SSOConfig(BaseModel):
    enabled: bool
    issuer: str
    client_id: str
    scopes: str
    redirect_uri: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/config", response_model=SSOConfig)
async def sso_config() -> SSOConfig:
    """Return SSO configuration for the frontend."""
    return SSOConfig(
        enabled=SSO_ENABLED,
        issuer=OIDC_ISSUER_URL,
        client_id=OIDC_CLIENT_ID,
        scopes=OIDC_SCOPES,
        redirect_uri=OIDC_REDIRECT_URI,
    )


@router.get("/initiate")
async def initiate_sso() -> RedirectResponse:
    """Redirect browser to OIDC provider authorization endpoint."""
    _require_sso()

    try:
        oidc_config = await _discover_oidc()
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"OIDC discovery failed: {exc}") from exc

    state = secrets.token_urlsafe(32)
    verifier, challenge = _pkce_pair()
    _state_store[state] = {"verifier": verifier}

    params = {
        "response_type": "code",
        "client_id": OIDC_CLIENT_ID,
        "redirect_uri": OIDC_REDIRECT_URI,
        "scope": OIDC_SCOPES,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    auth_url = f"{oidc_config['authorization_endpoint']}?{urlencode(params)}"
    return RedirectResponse(url=auth_url, status_code=302)


@router.get("/callback", response_model=TokenResponse)
async def sso_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: DbDep = None,  # type: ignore[assignment]
) -> TokenResponse:
    """Exchange OIDC authorization code for tokens, provision user if new."""
    _require_sso()

    state_data = _state_store.pop(state, None)
    if state_data is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired state.")

    try:
        oidc_config = await _discover_oidc()
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"OIDC discovery failed: {exc}") from exc

    # Exchange code → tokens
    async with httpx.AsyncClient(timeout=15) as client:
        token_resp = await client.post(
            oidc_config["token_endpoint"],
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": OIDC_REDIRECT_URI,
                "client_id": OIDC_CLIENT_ID,
                "client_secret": OIDC_CLIENT_SECRET,
                "code_verifier": state_data["verifier"],
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if not token_resp.is_success:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Token exchange failed.")
        tokens = token_resp.json()

        # Fetch userinfo
        userinfo_resp = await client.get(
            oidc_config["userinfo_endpoint"],
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        userinfo_resp.raise_for_status()
        userinfo = userinfo_resp.json()

    email: str = userinfo.get("email", "")
    if not email:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="OIDC provider did not return email.")

    # Provision or fetch user
    stmt = select(UserModel).where(UserModel.email == email)
    user_row = (await db.execute(stmt)).scalar_one_or_none()

    if user_row is None:
        import bcrypt
        user_row = UserModel(
            email=email,
            hashed_password=bcrypt.hashpw(secrets.token_bytes(32), bcrypt.gensalt()).decode(),
            subscription_tier="free",
            created_at=datetime.now(timezone.utc),
        )
        db.add(user_row)
        await db.flush()
        await log.ainfo("sso_user_provisioned", email=email)
    else:
        await log.ainfo("sso_user_login", email=email)

    await db.commit()

    access_token = create_access_token({"sub": str(user_row.id), "email": email})
    return TokenResponse(
        access_token=access_token,
        user_id=str(user_row.id),
        email=email,
    )


# ---------------------------------------------------------------------------
# SAML 2.0 stub
# ---------------------------------------------------------------------------


@router.get("/saml/metadata")
async def saml_metadata() -> dict[str, str]:
    """Return SP metadata XML (stub — requires python3-saml)."""
    _require_sso()
    return {
        "status": "stub",
        "note": "Install python3-saml and configure SAML_CERT / SAML_IDP_METADATA_URL to enable SAML 2.0.",
    }
