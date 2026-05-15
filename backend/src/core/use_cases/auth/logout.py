"""Use case: log out by blacklisting the access token and revoking the refresh token."""

import time

from src.core.ports.token_service import IRefreshTokenRepository, ITokenBlacklist, ITokenService


class LogoutCommand:
    def __init__(self, access_token: str, refresh_token: str | None = None):
        self.access_token = access_token
        self.refresh_token = refresh_token


class LogoutUseCase:
    def __init__(
        self,
        token_service: ITokenService,
        token_blacklist: ITokenBlacklist,
        refresh_token_repo: IRefreshTokenRepository,
    ):
        self._token_service = token_service
        self._blacklist = token_blacklist
        self._refresh_repo = refresh_token_repo

    async def execute(self, command: LogoutCommand) -> None:
        # Blacklist access token via its jti (TTL = remaining token lifetime).
        # Using jti instead of the full token string saves ~90 % Redis memory per entry.
        try:
            payload = self._token_service.decode_access_token(command.access_token)
            remaining = max(0, payload.exp - int(time.time()))
            await self._blacklist.blacklist(payload.jti, ttl_seconds=remaining)
        except Exception:
            pass  # Token already expired or invalid — nothing to blacklist

        # Revoke refresh token if provided
        if command.refresh_token:
            token_hash = self._token_service.hash_token(command.refresh_token)
            await self._refresh_repo.revoke(token_hash)
