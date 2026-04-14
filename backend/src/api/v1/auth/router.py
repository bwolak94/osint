"""Authentication endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.v1.auth.schemas import LoginRequest, RegisterRequest, TokenResponse
from src.config import Settings
from src.dependencies import get_app_settings

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> TokenResponse:
    """Register a new user account.

    Stub: in production, hash the password, persist the user, and issue a JWT.
    """
    # TODO: implement actual registration logic
    _ = settings
    return TokenResponse(
        access_token="stub-access-token",
        refresh_token="stub-refresh-token",
        token_type="bearer",
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> TokenResponse:
    """Authenticate a user and return tokens.

    Stub: in production, verify credentials against the database.
    """
    _ = settings
    return TokenResponse(
        access_token="stub-access-token",
        refresh_token="stub-refresh-token",
        token_type="bearer",
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> TokenResponse:
    """Refresh an access token.

    Stub: in production, validate the refresh token and issue new tokens.
    """
    _ = settings
    return TokenResponse(
        access_token="stub-new-access-token",
        refresh_token="stub-new-refresh-token",
        token_type="bearer",
    )
