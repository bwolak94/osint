"""Unit tests for the RegisterUserUseCase."""

import pytest

from src.core.domain.entities.types import SubscriptionTier
from src.core.domain.events.auth import UserRegistered
from src.core.use_cases.auth.register import RegisterUserUseCase, RegisterCommand
from tests.unit.use_cases.fakes import (
    FakeUserRepository,
    FakePasswordHasher,
    FakeTokenService,
    FakeEventPublisher,
)


class TestRegisterUseCase:
    @pytest.fixture
    def deps(self):
        return {
            "user_repo": FakeUserRepository(),
            "token_service": FakeTokenService(),
            "password_hasher": FakePasswordHasher(),
            "event_publisher": FakeEventPublisher(),
        }

    @pytest.mark.asyncio
    async def test_successful_registration(self, deps):
        uc = RegisterUserUseCase(**deps)
        result = await uc.execute(RegisterCommand(email="new@example.com", password="securepass123"))
        assert result.user.email.value == "new@example.com"
        assert result.tokens.access_token.startswith("access_")

    @pytest.mark.asyncio
    async def test_duplicate_email_raises(self, deps):
        uc = RegisterUserUseCase(**deps)
        await uc.execute(RegisterCommand(email="dup@example.com", password="pass12345"))
        with pytest.raises(ValueError, match="already exists"):
            await uc.execute(RegisterCommand(email="dup@example.com", password="pass12345"))

    @pytest.mark.asyncio
    async def test_publishes_user_registered_event(self, deps):
        uc = RegisterUserUseCase(**deps)
        await uc.execute(RegisterCommand(email="event@example.com", password="pass12345"))
        assert any(isinstance(e, UserRegistered) for e in deps["event_publisher"].events)

    @pytest.mark.asyncio
    async def test_invalid_email_raises(self, deps):
        uc = RegisterUserUseCase(**deps)
        with pytest.raises(ValueError):
            await uc.execute(RegisterCommand(email="not-an-email", password="pass12345"))

    @pytest.mark.asyncio
    async def test_user_created_with_free_tier(self, deps):
        uc = RegisterUserUseCase(**deps)
        result = await uc.execute(RegisterCommand(email="free@example.com", password="pass12345"))
        assert result.user.subscription_tier == SubscriptionTier.FREE

    @pytest.mark.asyncio
    async def test_user_is_active_after_registration(self, deps):
        uc = RegisterUserUseCase(**deps)
        result = await uc.execute(RegisterCommand(email="active@example.com", password="pass12345"))
        assert result.user.is_active is True

    @pytest.mark.asyncio
    async def test_user_persisted_in_repository(self, deps):
        uc = RegisterUserUseCase(**deps)
        result = await uc.execute(RegisterCommand(email="saved@example.com", password="pass12345"))
        from src.core.domain.value_objects.email import Email
        stored = await deps["user_repo"].get_by_email(Email("saved@example.com"))
        assert stored is not None
        assert stored.id == result.user.id

    @pytest.mark.asyncio
    async def test_password_is_hashed(self, deps):
        uc = RegisterUserUseCase(**deps)
        result = await uc.execute(RegisterCommand(email="hash@example.com", password="mypassword"))
        assert result.user.hashed_password == "hashed_mypassword"

    @pytest.mark.asyncio
    async def test_refresh_token_returned(self, deps):
        uc = RegisterUserUseCase(**deps)
        result = await uc.execute(RegisterCommand(email="tok@example.com", password="pass12345"))
        assert result.tokens.refresh_token.startswith("refresh_")

    @pytest.mark.asyncio
    async def test_email_not_verified_after_registration(self, deps):
        uc = RegisterUserUseCase(**deps)
        result = await uc.execute(RegisterCommand(email="unverified@example.com", password="pass12345"))
        assert result.user.is_email_verified is False
