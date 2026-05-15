"""Ports for token management: creation, validation, storage, and blacklisting."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


@dataclass(frozen=True)
class AccessTokenPayload:
    sub: str  # user_id as string
    email: str
    role: str
    subscription_tier: str
    exp: int  # unix timestamp
    jti: str  # JWT ID — used as the Redis blacklist key (avoids storing the full token)


@dataclass
class RefreshTokenRecord:
    id: UUID
    user_id: UUID
    token_hash: str
    family: str
    is_revoked: bool
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None
    ip_address: str | None = None
    user_agent: str | None = None


class ITokenService(Protocol):
    def create_access_token(self, user_id: UUID, email: str, role: str, tier: str) -> str: ...
    def create_refresh_token(self) -> str: ...
    def decode_access_token(self, token: str) -> AccessTokenPayload: ...
    def hash_token(self, token: str) -> str: ...


class ITokenBlacklist(Protocol):
    async def blacklist(self, jti: str, ttl_seconds: int) -> None: ...
    async def is_blacklisted(self, jti: str) -> bool: ...


class IRefreshTokenRepository(Protocol):
    async def save(
        self,
        user_id: UUID,
        token_hash: str,
        family: str,
        expires_at: datetime,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None: ...

    async def get_by_hash(self, token_hash: str) -> RefreshTokenRecord | None: ...
    async def revoke(self, token_hash: str) -> None: ...
    async def revoke_family(self, family: str) -> None: ...
    async def revoke_all_for_user(self, user_id: UUID) -> None: ...
