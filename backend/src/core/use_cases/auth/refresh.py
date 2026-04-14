"""Use case: rotate a refresh token and issue a new token pair."""

from datetime import datetime, timedelta, timezone

from src.core.domain.events.auth import RefreshTokenReused
from src.core.ports.event_publisher import IEventPublisher
from src.core.ports.repositories import IUserRepository
from src.core.ports.token_service import IRefreshTokenRepository, ITokenService, TokenPair
from src.core.use_cases.auth.exceptions import SecurityAlert, TokenError


class RefreshCommand:
    def __init__(
        self,
        refresh_token: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ):
        self.refresh_token = refresh_token
        self.ip_address = ip_address
        self.user_agent = user_agent


class RefreshResult:
    def __init__(self, tokens: TokenPair):
        self.tokens = tokens


class RefreshTokenUseCase:
    def __init__(
        self,
        user_repo: IUserRepository,
        token_service: ITokenService,
        refresh_token_repo: IRefreshTokenRepository,
        event_publisher: IEventPublisher,
    ):
        self._user_repo = user_repo
        self._token_service = token_service
        self._refresh_repo = refresh_token_repo
        self._event_publisher = event_publisher

    async def execute(self, command: RefreshCommand) -> RefreshResult:
        token_hash = self._token_service.hash_token(command.refresh_token)
        record = await self._refresh_repo.get_by_hash(token_hash)

        if record is None:
            raise TokenError("Invalid refresh token")

        # REUSE DETECTION: if token is already revoked, someone is reusing it
        if record.is_revoked:
            # Revoke entire family
            await self._refresh_repo.revoke_family(record.family)
            await self._event_publisher.publish(
                RefreshTokenReused(
                    user_id=record.user_id,
                    token_family=record.family,
                    ip_address=command.ip_address or "unknown",
                )
            )
            raise SecurityAlert("Refresh token reuse detected — all sessions revoked")

        # Check expiry
        if record.expires_at < datetime.now(timezone.utc):
            await self._refresh_repo.revoke(token_hash)
            raise TokenError("Refresh token has expired")

        # Get user
        user = await self._user_repo.get_by_id(record.user_id)
        if user is None or not user.is_active:
            raise TokenError("User not found or deactivated")

        # Revoke old token
        await self._refresh_repo.revoke(token_hash)

        # Issue new pair
        access_token = self._token_service.create_access_token(
            user_id=user.id,
            email=str(user.email),
            role=user.role.value,
            tier=user.subscription_tier.value,
        )
        new_refresh = self._token_service.create_refresh_token()
        new_hash = self._token_service.hash_token(new_refresh)

        expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        # Same family for rotation tracking
        await self._refresh_repo.save(
            user_id=user.id,
            token_hash=new_hash,
            family=record.family,
            expires_at=expires_at,
            ip_address=command.ip_address,
            user_agent=command.user_agent,
        )

        return RefreshResult(
            tokens=TokenPair(access_token=access_token, refresh_token=new_refresh)
        )
