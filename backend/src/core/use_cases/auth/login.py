"""Use case: authenticate a user with email and password."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from src.core.domain.entities.user import User
from src.core.domain.events.auth import AccountLocked, UserLoggedIn
from src.core.domain.value_objects.email import Email
from src.core.ports.event_publisher import IEventPublisher
from src.core.ports.password_hasher import IPasswordHasher
from src.core.ports.repositories import IUserRepository
from src.core.ports.token_service import IRefreshTokenRepository, ITokenService, TokenPair
from src.core.use_cases.auth.exceptions import AccountLockedError, AuthenticationError


@dataclass(frozen=True)
class LoginCommand:
    email: str
    password: str
    ip_address: str | None = None
    user_agent: str | None = None


class LoginResult:
    def __init__(self, user: User, tokens: TokenPair):
        self.user = user
        self.tokens = tokens


class LoginUseCase:
    def __init__(
        self,
        user_repo: IUserRepository,
        token_service: ITokenService,
        refresh_token_repo: IRefreshTokenRepository,
        password_hasher: IPasswordHasher,
        event_publisher: IEventPublisher,
    ):
        self._user_repo = user_repo
        self._token_service = token_service
        self._refresh_repo = refresh_token_repo
        self._password_hasher = password_hasher
        self._event_publisher = event_publisher

    async def execute(self, command: LoginCommand) -> LoginResult:
        # Find user
        email = Email(command.email)
        user = await self._user_repo.get_by_email(email)
        if user is None:
            raise AuthenticationError("Invalid email or password")

        # Check active
        if not user.is_active:
            raise AuthenticationError("Account is deactivated")

        # Check locked
        if user.is_locked():
            raise AccountLockedError(
                "Account is temporarily locked due to too many failed login attempts"
            )

        # Verify password
        if not self._password_hasher.verify(command.password, user.hashed_password):
            # Record failed attempt
            updated_user = user.record_failed_login()
            await self._user_repo.save(updated_user)

            if updated_user.is_locked():
                await self._event_publisher.publish(
                    AccountLocked(
                        user_id=user.id,
                        failed_attempts=updated_user.failed_login_attempts,
                        locked_until_minutes=15,
                    )
                )

            raise AuthenticationError("Invalid email or password")

        # Success — reset counter
        updated_user = user.record_successful_login()
        await self._user_repo.save(updated_user)

        # Create tokens
        access_token = self._token_service.create_access_token(
            user_id=user.id,
            email=str(user.email),
            role=user.role.value,
            tier=user.subscription_tier.value,
        )
        refresh_token = self._token_service.create_refresh_token()
        token_hash = self._token_service.hash_token(refresh_token)

        # Store refresh token with a new family
        family = uuid4().hex
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        await self._refresh_repo.save(
            user_id=user.id,
            token_hash=token_hash,
            family=family,
            expires_at=expires_at,
            ip_address=command.ip_address,
            user_agent=command.user_agent,
        )

        # Publish event
        await self._event_publisher.publish(
            UserLoggedIn(user_id=user.id, ip_address=command.ip_address or "unknown")
        )

        return LoginResult(
            user=updated_user,
            tokens=TokenPair(access_token=access_token, refresh_token=refresh_token),
        )
