"""Auth-related Pydantic schemas."""

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    """Payload for user login."""

    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    """Payload for user registration."""

    email: EmailStr
    password: str
    password_confirm: str


class TokenResponse(BaseModel):
    """JWT token pair response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
