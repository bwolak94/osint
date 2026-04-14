"""Authentication and authorization domain events."""

from dataclasses import dataclass
from uuid import UUID

from src.core.domain.events.base import DomainEvent


@dataclass(frozen=True)
class UserRegistered(DomainEvent):
    user_id: UUID
    email: str


@dataclass(frozen=True)
class UserLoggedIn(DomainEvent):
    user_id: UUID
    ip_address: str


@dataclass(frozen=True)
class UserLoggedOut(DomainEvent):
    user_id: UUID


@dataclass(frozen=True)
class PasswordChanged(DomainEvent):
    user_id: UUID


@dataclass(frozen=True)
class AccountLocked(DomainEvent):
    user_id: UUID
    failed_attempts: int
    locked_until_minutes: int


@dataclass(frozen=True)
class RefreshTokenReused(DomainEvent):
    """Security alert: someone tried to reuse a revoked refresh token."""
    user_id: UUID
    token_family: str
    ip_address: str
