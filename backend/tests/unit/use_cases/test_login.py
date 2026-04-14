"""Unit tests for the LoginUseCase."""

import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from src.core.domain.entities.user import User
from src.core.domain.entities.types import UserRole, SubscriptionTier
from src.core.domain.events.auth import UserLoggedIn, AccountLocked
from src.core.domain.value_objects.email import Email
from src.core.use_cases.auth.login import LoginUseCase, LoginCommand
from src.core.use_cases.auth.exceptions import AuthenticationError, AccountLockedError
from tests.unit.use_cases.fakes import (
    FakeUserRepository,
    FakePasswordHasher,
    FakeTokenService,
    FakeRefreshTokenRepository,
    FakeEventPublisher,
)


def make_user(
    email="user@example.com",
    password="correct",
    is_active=True,
    failed_attempts=0,
    locked_until=None,
):
    hasher = FakePasswordHasher()
    return User(
        id=uuid4(),
        email=Email(email),
        hashed_password=hasher.hash(password),
        role=UserRole.ANALYST,
        subscription_tier=SubscriptionTier.PRO,
        is_active=is_active,
        is_email_verified=True,
        failed_login_attempts=failed_attempts,
        locked_until=locked_until,
        last_login_at=None,
        created_at=datetime.now(timezone.utc),
    )


class TestLoginUseCase:
    @pytest.fixture
    def deps(self):
        return {
            "user_repo": FakeUserRepository(),
            "token_service": FakeTokenService(),
            "refresh_token_repo": FakeRefreshTokenRepository(),
            "password_hasher": FakePasswordHasher(),
            "event_publisher": FakeEventPublisher(),
        }

    @pytest.mark.asyncio
    async def test_successful_login_returns_tokens(self, deps):
        user = make_user()
        deps["user_repo"].add(user)
        uc = LoginUseCase(**deps)
        result = await uc.execute(LoginCommand(email="user@example.com", password="correct"))
        assert result.tokens.access_token is not None
        assert result.user.failed_login_attempts == 0

    @pytest.mark.asyncio
    async def test_wrong_password_increments_counter(self, deps):
        user = make_user()
        deps["user_repo"].add(user)
        uc = LoginUseCase(**deps)
        with pytest.raises(AuthenticationError):
            await uc.execute(LoginCommand(email="user@example.com", password="wrong"))
        # Check that failed attempts incremented
        updated = await deps["user_repo"].get_by_email(Email("user@example.com"))
        assert updated.failed_login_attempts == 1

    @pytest.mark.asyncio
    async def test_account_locked_after_5_attempts(self, deps):
        user = make_user(failed_attempts=4)
        deps["user_repo"].add(user)
        uc = LoginUseCase(**deps)
        with pytest.raises(AuthenticationError):
            await uc.execute(LoginCommand(email="user@example.com", password="wrong"))
        updated = await deps["user_repo"].get_by_email(Email("user@example.com"))
        assert updated.is_locked() is True

    @pytest.mark.asyncio
    async def test_locked_account_returns_locked_error(self, deps):
        user = make_user(locked_until=datetime.now(timezone.utc) + timedelta(minutes=15))
        deps["user_repo"].add(user)
        uc = LoginUseCase(**deps)
        with pytest.raises(AccountLockedError):
            await uc.execute(LoginCommand(email="user@example.com", password="correct"))

    @pytest.mark.asyncio
    async def test_inactive_user_cannot_login(self, deps):
        user = make_user(is_active=False)
        deps["user_repo"].add(user)
        uc = LoginUseCase(**deps)
        with pytest.raises(AuthenticationError):
            await uc.execute(LoginCommand(email="user@example.com", password="correct"))

    @pytest.mark.asyncio
    async def test_nonexistent_user_raises(self, deps):
        uc = LoginUseCase(**deps)
        with pytest.raises(AuthenticationError):
            await uc.execute(LoginCommand(email="nobody@example.com", password="anything"))

    @pytest.mark.asyncio
    async def test_successful_login_resets_counter(self, deps):
        user = make_user(failed_attempts=3)
        deps["user_repo"].add(user)
        uc = LoginUseCase(**deps)
        result = await uc.execute(LoginCommand(email="user@example.com", password="correct"))
        assert result.user.failed_login_attempts == 0

    @pytest.mark.asyncio
    async def test_publishes_login_event(self, deps):
        user = make_user()
        deps["user_repo"].add(user)
        uc = LoginUseCase(**deps)
        await uc.execute(
            LoginCommand(email="user@example.com", password="correct", ip_address="1.2.3.4")
        )
        assert any(isinstance(e, UserLoggedIn) for e in deps["event_publisher"].events)

    @pytest.mark.asyncio
    async def test_publishes_account_locked_event_on_5th_failure(self, deps):
        user = make_user(failed_attempts=4)
        deps["user_repo"].add(user)
        uc = LoginUseCase(**deps)
        with pytest.raises(AuthenticationError):
            await uc.execute(LoginCommand(email="user@example.com", password="wrong"))
        assert any(isinstance(e, AccountLocked) for e in deps["event_publisher"].events)

    @pytest.mark.asyncio
    async def test_successful_login_sets_last_login_at(self, deps):
        user = make_user()
        deps["user_repo"].add(user)
        uc = LoginUseCase(**deps)
        result = await uc.execute(LoginCommand(email="user@example.com", password="correct"))
        assert result.user.last_login_at is not None

    @pytest.mark.asyncio
    async def test_refresh_token_stored(self, deps):
        user = make_user()
        deps["user_repo"].add(user)
        uc = LoginUseCase(**deps)
        result = await uc.execute(LoginCommand(email="user@example.com", password="correct"))
        # The refresh token should have been stored in the repo
        rt_hash = deps["token_service"].hash_token(result.tokens.refresh_token)
        record = await deps["refresh_token_repo"].get_by_hash(rt_hash)
        assert record is not None
        assert record.user_id == user.id
