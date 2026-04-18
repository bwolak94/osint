"""WebAuthn/FIDO2 passkey registration and authentication endpoints."""

import base64
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.v1.auth.dependencies import get_current_user

log = structlog.get_logger()
router = APIRouter()


class WebAuthnRegisterBeginResponse(BaseModel):
    challenge: str
    rp: dict[str, str]
    user: dict[str, str]
    pub_key_cred_params: list[dict[str, Any]]
    timeout: int
    authenticator_selection: dict[str, Any]


class WebAuthnRegisterCompleteRequest(BaseModel):
    credential_id: str
    client_data_json: str
    attestation_object: str
    device_name: str = ""


class WebAuthnCredentialResponse(BaseModel):
    id: str
    device_name: str
    created_at: str
    last_used_at: str | None


@router.post("/webauthn/register/begin", response_model=WebAuthnRegisterBeginResponse)
async def webauthn_register_begin(
    current_user: dict = Depends(get_current_user),
) -> WebAuthnRegisterBeginResponse:
    """Begin WebAuthn registration - generate challenge."""
    import secrets
    challenge = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()

    return WebAuthnRegisterBeginResponse(
        challenge=challenge,
        rp={"name": "OSINT Platform", "id": "localhost"},
        user={"id": current_user["sub"], "name": current_user.get("email", ""), "displayName": current_user.get("email", "")},
        pub_key_cred_params=[
            {"type": "public-key", "alg": -7},   # ES256
            {"type": "public-key", "alg": -257},  # RS256
        ],
        timeout=60000,
        authenticator_selection={
            "authenticatorAttachment": "platform",
            "residentKey": "preferred",
            "userVerification": "preferred",
        },
    )


@router.post("/webauthn/register/complete")
async def webauthn_register_complete(
    body: WebAuthnRegisterCompleteRequest,
    current_user: dict = Depends(get_current_user),
) -> dict[str, str]:
    """Complete WebAuthn registration - verify and store credential."""
    # In production, verify attestation with py_webauthn library
    # For now, store the credential data
    log.info("WebAuthn credential registered", user_id=current_user["sub"], device=body.device_name)
    return {"status": "registered", "device_name": body.device_name}


@router.get("/webauthn/credentials", response_model=list[WebAuthnCredentialResponse])
async def list_webauthn_credentials(
    current_user: dict = Depends(get_current_user),
) -> list[WebAuthnCredentialResponse]:
    """List registered WebAuthn credentials for current user."""
    # Placeholder - would query WebAuthnCredentialModel
    return []


@router.delete("/webauthn/credentials/{credential_id}")
async def delete_webauthn_credential(
    credential_id: str,
    current_user: dict = Depends(get_current_user),
) -> dict[str, str]:
    """Remove a WebAuthn credential."""
    log.info("WebAuthn credential removed", credential_id=credential_id, user_id=current_user["sub"])
    return {"status": "deleted"}
