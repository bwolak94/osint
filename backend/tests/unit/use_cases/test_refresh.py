"""Unit tests for the RefreshTokenUseCase."""

import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from src.core.domain.entities.user import User
from src.core.domain.entities.types import UserRole, SubscriptionTier
from src.core.domain.events.auth import RefreshTokenReused
from src.core.domain.value_objects.email import Email
from src.core.use_cases.auth.refresh import RefreshTokenUseCase, RefreshCommand
from src.core.use_cases.auth.exceptions import TokenError, SecurityAlert
from tests.unit.use_cases.fakes import (
    FakeUserRepository,
    FakeTokenService,
    FakeRefreshTokenRepository,
    FakeEventPublisher,
)


def make_user(user_id=None):
    return User(
        id=user_id or uuid4(),
        email=Email("user@example.com"),
        hashed_password="hashed",
        role=UserRole.ANALYST,
        subscription_tier=SubscriptionTier.PRO,
        is_active=True,
        is_email_verified=True,
        failed_login_attempts=0,
        locked_until=None,
        last_login_at=None,
        created_at=datetime.now(timezone.utc),
    )


class TestRefreshTokenUseCase:
    @pytest.fixture
    def deps(self):
        return {
            "user_repo": FakeUserRepository(),
            "token_service": FakeTokenService(),
            "refresh_token_repo": FakeRefreshTokenRepository(),
            "event_publisher": FakeEventPublisher(),
        }

    @pytest.mark.asyncio
    async def test_valid_refresh_returns_new_tokens(self, deps):
        user = make_user()
        deps["user_repo"].add(user)
        # Store a refresh token
        token = "valid-refresh-token"
        token_hash = deps["token_service"].hash_token(token)
        await deps["refresh_token_repo"].save(
            user_id=user.id,
            token_hash=token_hash,
            family="fam1",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )

        uc = RefreshTokenUseCase(**deps)
        result = await uc.execute(RefreshCommand(refresh_token=token))
        assert result.tokens.access_token is not None

    @pytest.mark.asyncio
    async def test_reuse_detection_revokes_family(self, deps):
        user = make_user()
        deps["user_repo"].add(user)
        token = "reused-token"
        token_hash = deps["token_service"].hash_token(token)
        await deps["refresh_token_repo"].save(
            user_id=user.id,
            token_hash=token_hash,
            family="fam1",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        # Revoke it (simulating it was already used)
        await deps["refresh_token_repo"].revoke(token_hash)

        uc = RefreshTokenUseCase(**deps)
        with pytest.raises(SecurityAlert):
            await uc.execute(RefreshCommand(refresh_token=token))

    @pytest.mark.asyncio
    async def test_expired_token_returns_error(self, deps):
        user = make_user()
        deps["user_repo"].add(user)
        token = "expired-token"
        token_hash = deps["token_service"].hash_token(token)
        await deps["refresh_token_repo"].save(
            user_id=user.id,
            token_hash=token_hash,
            family="fam1",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),  # expired
        )

        uc = RefreshTokenUseCase(**deps)
        with pytest.raises(TokenError):
            await uc.execute(RefreshCommand(refresh_token=token))

    @pytest.mark.asyncio
    async def test_invalid_token_raises(self, deps):
        uc = RefreshTokenUseCase(**deps)
        with pytest.raises(TokenError):
            await uc.execute(RefreshCommand(refresh_token="nonexistent"))

    @pytest.mark.asyncio
    async def test_old_token_revoked_after_refresh(self, deps):
        user = make_user()
        deps["user_repo"].add(user)
        token = "to-be-rotated"
        token_hash = deps["token_service"].hash_token(token)
        await deps["refresh_token_repo"].save(
            user_id=user.id,
            token_hash=token_hash,
            family="fam1",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )

        uc = RefreshTokenUseCase(**deps)
        await uc.execute(RefreshCommand(refresh_token=token))

        # Old token should now be revoked
        old_record = await deps["refresh_token_repo"].get_by_hash(token_hash)
        assert old_record.is_revoked is True

    @pytest.mark.asyncio
    async def test_new_token_uses_same_family(self, deps):
        user = make_user()
        deps["user_repo"].add(user)
        token = "family-check"
        token_hash = deps["token_service"].hash_token(token)
        await deps["refresh_token_repo"].save(
            user_id=user.id,
            token_hash=token_hash,
            family="my-family",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )

        uc = RefreshTokenUseCase(**deps)
        result = await uc.execute(RefreshCommand(refresh_token=token))

        # New refresh token should be stored with the same family
        new_hash = deps["token_service"].hash_token(result.tokens.refresh_token)
        new_record = await deps["refresh_token_repo"].get_by_hash(new_hash)
        assert new_record is not None
        assert new_record.family == "my-family"

    @pytest.mark.asyncio
    async def test_reuse_publishes_security_event(self, deps):
        user = make_user()
        deps["user_repo"].add(user)
        token = "reuse-event-token"
        token_hash = deps["token_service"].hash_token(token)
        await deps["refresh_token_repo"].save(
            user_id=user.id,
            token_hash=token_hash,
            family="fam2",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        await deps["refresh_token_repo"].revoke(token_hash)

        uc = RefreshTokenUseCase(**deps)
        with pytest.raises(SecurityAlert):
            await uc.execute(RefreshCommand(refresh_token=token))

        assert any(isinstance(e, RefreshTokenReused) for e in deps["event_publisher"].events)

    @pytest.mark.asyncio
    async def test_inactive_user_raises(self, deps):
        user = make_user()
        # Deactivate the user
        user.is_active = False
        deps["user_repo"].add(user)
        token = "inactive-user-token"
        token_hash = deps["token_service"].hash_token(token)
        await deps["refresh_token_repo"].save(
            user_id=user.id,
            token_hash=token_hash,
            family="fam3",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )

        uc = RefreshTokenUseCase(**deps)
        with pytest.raises(TokenError):
            await uc.execute(RefreshCommand(refresh_token=token))
