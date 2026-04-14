"""Unit tests for the LogoutUseCase."""

import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from src.core.use_cases.auth.logout import LogoutUseCase, LogoutCommand
from tests.unit.use_cases.fakes import (
    FakeTokenService,
    FakeTokenBlacklist,
    FakeRefreshTokenRepository,
)


class TestLogoutUseCase:
    @pytest.mark.asyncio
    async def test_blacklists_access_token(self):
        blacklist = FakeTokenBlacklist()
        uc = LogoutUseCase(
            token_service=FakeTokenService(),
            token_blacklist=blacklist,
            refresh_token_repo=FakeRefreshTokenRepository(),
        )
        await uc.execute(LogoutCommand(access_token="my-access-token"))
        assert await blacklist.is_blacklisted("my-access-token")

    @pytest.mark.asyncio
    async def test_revokes_refresh_token(self):
        refresh_repo = FakeRefreshTokenRepository()
        token_service = FakeTokenService()
        # Pre-store a refresh token
        rt = "my-refresh-token"
        rt_hash = token_service.hash_token(rt)
        await refresh_repo.save(
            user_id=uuid4(),
            token_hash=rt_hash,
            family="fam1",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )

        uc = LogoutUseCase(
            token_service=token_service,
            token_blacklist=FakeTokenBlacklist(),
            refresh_token_repo=refresh_repo,
        )
        await uc.execute(LogoutCommand(access_token="access", refresh_token=rt))

        record = await refresh_repo.get_by_hash(rt_hash)
        assert record.is_revoked is True

    @pytest.mark.asyncio
    async def test_logout_without_refresh_token(self):
        blacklist = FakeTokenBlacklist()
        refresh_repo = FakeRefreshTokenRepository()
        uc = LogoutUseCase(
            token_service=FakeTokenService(),
            token_blacklist=blacklist,
            refresh_token_repo=refresh_repo,
        )
        # Should not raise even without a refresh token
        await uc.execute(LogoutCommand(access_token="some-access-token"))
        assert await blacklist.is_blacklisted("some-access-token")

    @pytest.mark.asyncio
    async def test_logout_with_expired_access_token_does_not_raise(self):
        """Even if decoding fails (expired token), logout should not raise."""
        token_service = FakeTokenService()

        # Override decode to simulate failure
        def bad_decode(token: str):
            raise Exception("Token expired")

        token_service.decode_access_token = bad_decode

        blacklist = FakeTokenBlacklist()
        uc = LogoutUseCase(
            token_service=token_service,
            token_blacklist=blacklist,
            refresh_token_repo=FakeRefreshTokenRepository(),
        )
        # Should not raise
        await uc.execute(LogoutCommand(access_token="expired-token"))
