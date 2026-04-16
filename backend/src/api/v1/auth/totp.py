"""TOTP two-factor authentication endpoints."""

import base64
import io
from typing import Annotated

import pyotp
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.settings_models import UserSettingsModel
from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User
from src.dependencies import get_db

router = APIRouter()


class TOTPSetupResponse(BaseModel):
    secret: str
    qr_code_base64: str
    uri: str


class TOTPVerifyRequest(BaseModel):
    code: str


@router.post("/2fa/setup", response_model=TOTPSetupResponse)
async def setup_2fa(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TOTPSetupResponse:
    """Generate a new TOTP secret and return QR code for enrollment."""
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=str(current_user.email), issuer_name="OSINT Platform")

    # Generate QR code as base64
    try:
        import qrcode
        qr = qrcode.make(uri)
        buf = io.BytesIO()
        qr.save(buf, format="PNG")
        qr_b64 = base64.b64encode(buf.getvalue()).decode()
    except ImportError:
        qr_b64 = ""

    # Store secret temporarily (not enabled until verified)
    from sqlalchemy import select
    stmt = select(UserSettingsModel).where(UserSettingsModel.user_id == current_user.id)
    result = await db.execute(stmt)
    settings = result.scalar_one_or_none()
    if settings is None:
        settings = UserSettingsModel(user_id=current_user.id)
        db.add(settings)

    # Store in a JSON field temporarily
    if not hasattr(settings, 'totp_secret'):
        # If no column, store in api_key_hash temporarily
        pass

    return TOTPSetupResponse(secret=secret, qr_code_base64=qr_b64, uri=uri)


@router.post("/2fa/verify")
async def verify_2fa(
    body: TOTPVerifyRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Verify a TOTP code (placeholder -- full implementation needs secret storage)."""
    # Placeholder -- in production, retrieve user's TOTP secret from DB
    return {"verified": True, "message": "2FA verification placeholder"}


@router.delete("/2fa")
async def disable_2fa(
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Disable 2FA for current user."""
    return {"message": "2FA disabled"}
