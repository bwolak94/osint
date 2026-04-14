"""Use case: register a new user account."""

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from src.core.domain.entities.types import SubscriptionTier, UserRole
from src.core.domain.entities.user import User
from src.core.domain.events.auth import UserRegistered
from src.core.domain.value_objects.email import Email
from src.core.ports.event_publisher import IEventPublisher
from src.core.ports.password_hasher import IPasswordHasher
from src.core.ports.repositories import IUserRepository
from src.core.ports.token_service import ITokenService, TokenPair


@dataclass(frozen=True)
class RegisterCommand:
    email: str
    password: str


class RegisterResult:
    def __init__(self, user: User, tokens: TokenPair):
        self.user = user
        self.tokens = tokens


class RegisterUserUseCase:
    def __init__(
        self,
        user_repo: IUserRepository,
        token_service: ITokenService,
        password_hasher: IPasswordHasher,
        event_publisher: IEventPublisher,
    ):
        self._user_repo = user_repo
        self._token_service = token_service
        self._password_hasher = password_hasher
        self._event_publisher = event_publisher

    async def execute(self, command: RegisterCommand) -> RegisterResult:
        # Validate email as value object
        email = Email(command.email)

        # Check if user exists
        existing = await self._user_repo.get_by_email(email)
        if existing is not None:
            raise ValueError("User with this email already exists")

        # Hash password
        hashed = self._password_hasher.hash(command.password)

        # Create user entity
        now = datetime.now(timezone.utc)
        user = User(
            id=uuid4(),
            email=email,
            hashed_password=hashed,
            role=UserRole.ANALYST,
            subscription_tier=SubscriptionTier.FREE,
            is_active=True,
            is_email_verified=False,
            failed_login_attempts=0,
            locked_until=None,
            last_login_at=None,
            created_at=now,
        )

        # Persist
        saved_user = await self._user_repo.save(user)

        # Create tokens
        access_token = self._token_service.create_access_token(
            user_id=saved_user.id,
            email=str(saved_user.email),
            role=saved_user.role.value,
            tier=saved_user.subscription_tier.value,
        )
        refresh_token = self._token_service.create_refresh_token()
        tokens = TokenPair(access_token=access_token, refresh_token=refresh_token)

        # Publish event
        await self._event_publisher.publish(
            UserRegistered(user_id=saved_user.id, email=str(saved_user.email))
        )

        return RegisterResult(user=saved_user, tokens=tokens)
