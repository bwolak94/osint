"""Fake implementations of ports for unit testing."""
from datetime import datetime, timezone
from uuid import UUID, uuid4

from src.core.domain.entities.user import User
from src.core.domain.entities.types import UserRole, SubscriptionTier
from src.core.domain.value_objects.email import Email
from src.core.domain.events.base import DomainEvent
from src.core.ports.token_service import RefreshTokenRecord


class FakeUserRepository:
    """In-memory user repository for tests."""

    def __init__(self):
        self._users: dict[UUID, User] = {}

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self._users.get(user_id)

    async def get_by_email(self, email: Email) -> User | None:
        for user in self._users.values():
            if user.email == email:
                return user
        return None

    async def save(self, user: User) -> User:
        self._users[user.id] = user
        return user

    async def delete(self, user_id: UUID) -> None:
        self._users.pop(user_id, None)

    def add(self, user: User) -> None:
        """Helper for test setup."""
        self._users[user.id] = user


class FakePasswordHasher:
    """Deterministic password hasher for tests."""

    def hash(self, password: str) -> str:
        return f"hashed_{password}"

    def verify(self, password: str, hashed: str) -> bool:
        return hashed == f"hashed_{password}"


class FakeTokenService:
    """Predictable token service for tests."""

    def __init__(self):
        self._counter = 0

    def create_access_token(self, user_id: UUID, email: str, role: str, tier: str) -> str:
        self._counter += 1
        return f"access_{self._counter}"

    def create_refresh_token(self) -> str:
        self._counter += 1
        return f"refresh_{self._counter}"

    def decode_access_token(self, token: str):
        from src.core.ports.token_service import AccessTokenPayload
        import time
        # Return a payload with exp in the future
        return AccessTokenPayload(
            sub="test-user-id",
            email="test@example.com",
            role="analyst",
            subscription_tier="free",
            exp=int(time.time()) + 3600,
        )

    def hash_token(self, token: str) -> str:
        return f"sha256_{token}"


class FakeRefreshTokenRepository:
    """In-memory refresh token store for tests."""

    def __init__(self):
        self._tokens: dict[str, RefreshTokenRecord] = {}

    async def save(
        self,
        user_id: UUID,
        token_hash: str,
        family: str,
        expires_at: datetime,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        self._tokens[token_hash] = RefreshTokenRecord(
            id=uuid4(),
            user_id=user_id,
            token_hash=token_hash,
            family=family,
            is_revoked=False,
            created_at=datetime.now(timezone.utc),
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def get_by_hash(self, token_hash: str) -> RefreshTokenRecord | None:
        return self._tokens.get(token_hash)

    async def revoke(self, token_hash: str) -> None:
        if token_hash in self._tokens:
            record = self._tokens[token_hash]
            self._tokens[token_hash] = RefreshTokenRecord(
                id=record.id,
                user_id=record.user_id,
                token_hash=record.token_hash,
                family=record.family,
                is_revoked=True,
                created_at=record.created_at,
                expires_at=record.expires_at,
                revoked_at=datetime.now(timezone.utc),
                ip_address=record.ip_address,
                user_agent=record.user_agent,
            )

    async def revoke_family(self, family: str) -> None:
        for hash_key, record in list(self._tokens.items()):
            if record.family == family and not record.is_revoked:
                await self.revoke(hash_key)

    async def revoke_all_for_user(self, user_id: UUID) -> None:
        for hash_key, record in list(self._tokens.items()):
            if record.user_id == user_id and not record.is_revoked:
                await self.revoke(hash_key)


class FakeEventPublisher:
    """Collects published events for assertions."""

    def __init__(self):
        self.events: list[DomainEvent] = []

    async def publish(self, event: DomainEvent) -> None:
        self.events.append(event)

    async def publish_many(self, events: list[DomainEvent]) -> None:
        self.events.extend(events)


class FakeTokenBlacklist:
    """In-memory token blacklist for tests."""

    def __init__(self):
        self._blacklisted: set[str] = set()

    async def blacklist(self, token: str, ttl_seconds: int) -> None:
        self._blacklisted.add(token)

    async def is_blacklisted(self, token: str) -> bool:
        return token in self._blacklisted
