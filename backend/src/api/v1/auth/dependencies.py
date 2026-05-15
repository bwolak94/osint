from typing import Annotated
from uuid import UUID

import json
from datetime import datetime, timezone

import structlog
from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.auth.password_hasher import BcryptPasswordHasher
from src.adapters.auth.token_service import JWTTokenService
from src.adapters.cache.token_blacklist import RedisTokenBlacklist
from src.adapters.db.refresh_token_repository import SqlAlchemyRefreshTokenRepository
from src.adapters.db.repositories import SqlAlchemyUserRepository
from src.config import Settings, get_settings
from src.core.domain.entities.types import Feature, SubscriptionTier, UserRole
from src.core.domain.entities.user import User
from src.core.domain.value_objects.email import Email
from src.core.ports.token_service import AccessTokenPayload
from src.dependencies import get_db

log = structlog.get_logger(__name__)

security = HTTPBearer(auto_error=False)

# Ordered list used for subscription tier comparison.
# If a tier is missing, require_subscription will raise a clear error rather
# than an opaque ValueError from list.index().
_TIER_ORDER = [SubscriptionTier.FREE, SubscriptionTier.PRO, SubscriptionTier.ENTERPRISE]
_TIER_RANK: dict[SubscriptionTier, int] = {tier: i for i, tier in enumerate(_TIER_ORDER)}


def get_token_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> JWTTokenService:
    return JWTTokenService(settings)


def get_password_hasher() -> BcryptPasswordHasher:
    return BcryptPasswordHasher()


async def get_redis(request: Request):
    """Get Redis from app state. Raises 503 if unavailable (fail-closed for auth paths)."""
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        raise HTTPException(status_code=503, detail="Redis not available")
    return redis


async def get_redis_optional(request: Request):
    """Get Redis from app state, returning None if unavailable. (#5)

    Use this for non-critical paths (rate limiting, feature flags) where a Redis
    outage should degrade gracefully rather than block the entire request.
    For auth paths (token blacklist), use ``get_redis`` to fail closed.
    """
    return getattr(request.app.state, "redis", None)


async def get_token_blacklist(redis=Depends(get_redis)) -> RedisTokenBlacklist:
    return RedisTokenBlacklist(redis)


async def get_user_repo(db=Depends(get_db)) -> SqlAlchemyUserRepository:
    return SqlAlchemyUserRepository(db)


async def get_refresh_token_repo(db=Depends(get_db)) -> SqlAlchemyRefreshTokenRepository:
    return SqlAlchemyRefreshTokenRepository(db)


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)] = None,
    token_service: Annotated[JWTTokenService, Depends(get_token_service)] = None,
    user_repo: Annotated[SqlAlchemyUserRepository, Depends(get_user_repo)] = None,
) -> User:
    """Decode JWT, check blacklist, return User entity.

    Fails closed when Redis is unavailable: revoked tokens are rejected with 503
    rather than silently accepted. This prevents a Redis outage from becoming a
    security bypass.
    """
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    token = credentials.credentials

    # Decode token — uses the injected token_service (avoids redundant instantiation).
    try:
        payload = token_service.decode_access_token(token)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    # Check blacklist via jti.  Fail closed: if Redis is down, reject the request
    # rather than silently accepting potentially revoked tokens.
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        log.warning("token_blacklist_unavailable", reason="Redis not in app state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable",
        )
    blacklist = RedisTokenBlacklist(redis)
    if payload.jti and await blacklist.is_blacklisted(payload.jti):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked")

    # User profile cache (#18): avoid a DB round-trip on every authenticated request.
    # Cache key: "user_profile:{user_id}" with 60-second TTL.
    # We do NOT cache hashed_password — it is reconstructed as "" since get_current_user
    # callers never need it (only LoginUseCase and ChangePasswordUseCase do).
    _USER_CACHE_TTL = 60
    user_cache_key = f"user_profile:{payload.sub}"
    cached_raw = await redis.get(user_cache_key)

    if cached_raw is not None:
        try:
            d = json.loads(cached_raw)
            from src.core.domain.value_objects.email import Email
            from src.core.domain.entities.types import UserRole, SubscriptionTier
            user = User(
                id=UUID(d["id"]),
                email=Email(d["email"]),
                hashed_password="",  # not cached — not used by get_current_user callers
                role=UserRole(d["role"]),
                subscription_tier=SubscriptionTier(d["subscription_tier"]),
                is_active=d["is_active"],
                is_email_verified=d["is_email_verified"],
                failed_login_attempts=d.get("failed_login_attempts", 0),
                created_at=datetime.fromisoformat(d["created_at"]),
                tos_accepted_at=datetime.fromisoformat(d["tos_accepted_at"]) if d.get("tos_accepted_at") else None,
            )
            if not user.is_active:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or deactivated")
            return user
        except Exception:
            # Corrupted cache entry — fall through to DB fetch
            pass

    # Cache miss: fetch from DB and populate cache.
    user = await user_repo.get_by_id(UUID(payload.sub))

    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or deactivated")

    # Serialize user profile to Redis (exclude hashed_password for security).
    try:
        cache_payload = json.dumps({
            "id": str(user.id),
            "email": str(user.email),
            "role": user.role.value,
            "subscription_tier": user.subscription_tier.value,
            "is_active": user.is_active,
            "is_email_verified": user.is_email_verified,
            "failed_login_attempts": user.failed_login_attempts,
            "created_at": user.created_at.isoformat(),
            "tos_accepted_at": user.tos_accepted_at.isoformat() if user.tos_accepted_at else None,
        })
        await redis.setex(user_cache_key, _USER_CACHE_TTL, cache_payload)
    except Exception as cache_err:
        log.warning("user_profile_cache_write_failed", user_id=str(user.id), error=str(cache_err))

    return user


def require_role(*roles: UserRole):
    """Factory: require_role(UserRole.ADMIN, UserRole.ANALYST)"""
    async def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_user
    return dependency


def require_subscription(*tiers: SubscriptionTier):
    """Factory: require_subscription(SubscriptionTier.PRO)

    ENTERPRISE includes all PRO features, so higher tiers are also accepted.
    Uses a pre-built rank dict so an unknown tier produces a clear KeyError
    rather than an opaque ValueError from list.index().
    """
    async def dependency(current_user: User = Depends(get_current_user)) -> User:
        user_rank = _TIER_RANK.get(current_user.subscription_tier)
        if user_rank is None:
            log.error(
                "unknown_subscription_tier",
                tier=current_user.subscription_tier,
                user_id=str(current_user.id),
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Subscription upgrade required",
                headers={"X-Upgrade-Required": "true"},
            )
        min_required_rank = min(
            _TIER_RANK[t] for t in tiers if t in _TIER_RANK
        )
        if user_rank < min_required_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Subscription upgrade required",
                headers={"X-Upgrade-Required": "true"},
            )
        return current_user
    return dependency


def require_feature(feature: Feature):
    """Most granular access control: require_feature(Feature.DEEP_SCAN)"""
    async def dependency(current_user: User = Depends(get_current_user)) -> User:
        if not current_user.can_use_feature(feature):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Feature '{feature.value}' requires a higher subscription tier",
                headers={"X-Upgrade-Required": "true"},
            )
        return current_user
    return dependency
