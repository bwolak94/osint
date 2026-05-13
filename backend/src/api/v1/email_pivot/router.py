"""FastAPI router — Email Pivot (Gravatar, GitHub, HIBP, disposable check)."""
from __future__ import annotations
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from src.adapters.email_pivot.fetcher import pivot_email
from src.api.v1.auth.dependencies import get_current_user
from src.api.v1.email_pivot.schemas import EmailPivotRequest, EmailPivotResponse, LinkedAccountSchema
from src.core.domain.entities.user import User

log = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/", response_model=EmailPivotResponse)
async def email_pivot(
    body: EmailPivotRequest,
    _: Annotated[User, Depends(get_current_user)],
) -> EmailPivotResponse:
    email = body.email.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email address.")

    info = await pivot_email(email, hibp_key=body.hibp_key)
    return EmailPivotResponse(
        email=info.email,
        domain=info.domain,
        gravatar_exists=info.gravatar_exists,
        gravatar_display_name=info.gravatar_display_name,
        gravatar_avatar_url=info.gravatar_avatar_url,
        gravatar_profile_url=info.gravatar_profile_url,
        github_username=info.github_username,
        github_profile_url=info.github_profile_url,
        hibp_breaches=info.hibp_breaches,
        hibp_checked=info.hibp_checked,
        disposable=info.disposable,
        linked_accounts=[
            LinkedAccountSchema(
                platform=a.platform,
                profile_url=a.profile_url,
                display_name=a.display_name,
                avatar_url=a.avatar_url,
                exists=a.exists,
            )
            for a in info.linked_accounts
        ],
    )
