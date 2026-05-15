"""Tests for the refresh token rotation and reuse-detection (token theft) flow.

The security invariant:
  - Using a valid refresh token → new token pair, old token revoked.
  - Reusing a revoked token → ENTIRE FAMILY revoked + SecurityAlert raised.
  - Expired token → TokenError raised, token revoked.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.core.use_cases.auth.refresh import RefreshCommand, RefreshTokenUseCase
from src.core.use_cases.auth.exceptions import SecurityAlert, TokenError
from src.core.ports.token_service import RefreshTokenRecord, TokenPair


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_record(
    *,
    is_revoked: bool = False,
    expires_at: datetime | None = None,
    family: str = "fam-1",
    user_id=None,
) -> RefreshTokenRecord:
    return RefreshTokenRecord(
        id=uuid4(),
        user_id=user_id or uuid4(),
        token_hash="hashed",
        family=family,
        is_revoked=is_revoked,
        created_at=datetime.now(timezone.utc),
        expires_at=expires_at or datetime.now(timezone.utc) + timedelta(days=7),
    )


def _make_use_case(record: RefreshTokenRecord | None, user_active: bool = True):
    """Build a RefreshTokenUseCase with mocked dependencies."""
    user = MagicMock()
    user.id = record.user_id if record else uuid4()
    user.is_active = user_active
    user.email = MagicMock(__str__=lambda self: "user@example.com")
    user.role = MagicMock(value="analyst")
    user.subscription_tier = MagicMock(value="free")

    token_service = MagicMock()
    token_service.hash_token.return_value = "hashed"
    token_service.create_access_token.return_value = "new-access-token"
    token_service.create_refresh_token.return_value = "new-refresh-token"

    refresh_repo = AsyncMock()
    refresh_repo.get_by_hash.return_value = record
    refresh_repo.revoke = AsyncMock(return_value=True)
    refresh_repo.revoke_family = AsyncMock()
    refresh_repo.save = AsyncMock()

    user_repo = AsyncMock()
    user_repo.get_by_id.return_value = user if user_active else None

    event_publisher = AsyncMock()
    event_publisher.publish = AsyncMock()

    use_case = RefreshTokenUseCase(
        user_repo=user_repo,
        token_service=token_service,
        refresh_token_repo=refresh_repo,
        event_publisher=event_publisher,
    )
    return use_case, refresh_repo, event_publisher


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

async def test_valid_token_returns_new_pair():
    record = _make_record()
    use_case, refresh_repo, _ = _make_use_case(record)

    result = await use_case.execute(RefreshCommand(refresh_token="raw-token"))

    assert result.tokens.access_token == "new-access-token"
    assert result.tokens.refresh_token == "new-refresh-token"
    refresh_repo.revoke.assert_awaited_once_with("hashed")
    refresh_repo.save.assert_awaited_once()


async def test_valid_token_preserves_family():
    record = _make_record(family="my-family")
    use_case, refresh_repo, _ = _make_use_case(record)

    await use_case.execute(RefreshCommand(refresh_token="raw-token"))

    save_kwargs = refresh_repo.save.call_args.kwargs
    assert save_kwargs["family"] == "my-family"


# ---------------------------------------------------------------------------
# Reuse / theft detection
# ---------------------------------------------------------------------------

async def test_revoked_token_raises_security_alert():
    record = _make_record(is_revoked=True)
    use_case, refresh_repo, event_publisher = _make_use_case(record)

    with pytest.raises(SecurityAlert):
        await use_case.execute(RefreshCommand(refresh_token="raw-token", ip_address="1.2.3.4"))


async def test_revoked_token_revokes_entire_family():
    record = _make_record(is_revoked=True, family="targeted-family")
    use_case, refresh_repo, _ = _make_use_case(record)

    with pytest.raises(SecurityAlert):
        await use_case.execute(RefreshCommand(refresh_token="raw-token"))

    refresh_repo.revoke_family.assert_awaited_once_with("targeted-family")


async def test_revoked_token_publishes_reuse_event():
    record = _make_record(is_revoked=True)
    use_case, _, event_publisher = _make_use_case(record)

    with pytest.raises(SecurityAlert):
        await use_case.execute(RefreshCommand(refresh_token="raw-token", ip_address="9.9.9.9"))

    event_publisher.publish.assert_awaited_once()
    published = event_publisher.publish.call_args.args[0]
    assert published.ip_address == "9.9.9.9"


async def test_revoked_token_does_not_issue_new_tokens():
    record = _make_record(is_revoked=True)
    use_case, refresh_repo, _ = _make_use_case(record)

    with pytest.raises(SecurityAlert):
        await use_case.execute(RefreshCommand(refresh_token="raw-token"))

    refresh_repo.save.assert_not_awaited()


# ---------------------------------------------------------------------------
# Token not found
# ---------------------------------------------------------------------------

async def test_unknown_token_raises_token_error():
    use_case, _, _ = _make_use_case(record=None)

    with pytest.raises(TokenError):
        await use_case.execute(RefreshCommand(refresh_token="unknown-token"))


# ---------------------------------------------------------------------------
# Expired token
# ---------------------------------------------------------------------------

async def test_expired_token_raises_token_error():
    record = _make_record(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    use_case, _, _ = _make_use_case(record)

    with pytest.raises(TokenError):
        await use_case.execute(RefreshCommand(refresh_token="raw-token"))


async def test_expired_token_is_revoked():
    record = _make_record(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    use_case, refresh_repo, _ = _make_use_case(record)

    with pytest.raises(TokenError):
        await use_case.execute(RefreshCommand(refresh_token="raw-token"))

    refresh_repo.revoke.assert_awaited_once_with("hashed")


# ---------------------------------------------------------------------------
# Deactivated user
# ---------------------------------------------------------------------------

async def test_deactivated_user_raises_token_error():
    record = _make_record()
    use_case, _, _ = _make_use_case(record, user_active=False)
    # Override: get_by_id returns None for deactivated user scenario
    use_case._user_repo.get_by_id.return_value = None

    with pytest.raises(TokenError):
        await use_case.execute(RefreshCommand(refresh_token="raw-token"))
