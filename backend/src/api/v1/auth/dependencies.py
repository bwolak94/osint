from typing import Annotated
from uuid import UUID

from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

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

security = HTTPBearer(auto_error=False)


def get_token_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> JWTTokenService:
    return JWTTokenService(settings)


def get_password_hasher() -> BcryptPasswordHasher:
    return BcryptPasswordHasher()


async def get_redis(request: Request):
    """Get Redis from app state (set during lifespan)."""
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        raise HTTPException(status_code=503, detail="Redis not available")
    return redis


async def get_token_blacklist(redis=Depends(get_redis)) -> RedisTokenBlacklist:
    return RedisTokenBlacklist(redis)


async def get_user_repo(db=Depends(get_db)) -> SqlAlchemyUserRepository:
    return SqlAlchemyUserRepository(db)


async def get_refresh_token_repo(db=Depends(get_db)) -> SqlAlchemyRefreshTokenRepository:
    return SqlAlchemyRefreshTokenRepository(db)


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)] = None,
    settings: Settings = Depends(get_settings),
) -> User:
    """Decode JWT, check blacklist, return User entity."""
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    token = credentials.credentials
    token_service = JWTTokenService(settings)

    # Decode token
    try:
        payload = token_service.decode_access_token(token)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    # Check blacklist
    redis = getattr(request.app.state, "redis", None)
    if redis is not None:
        blacklist = RedisTokenBlacklist(redis)
        if await blacklist.is_blacklisted(token):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked")

    # Get user from DB
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.adapters.db.database import async_session_factory

    async with async_session_factory() as session:
        repo = SqlAlchemyUserRepository(session)
        user = await repo.get_by_id(UUID(payload.sub))

    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or deactivated")

    return user


def require_role(*roles: UserRole):
    """Factory: require_role(UserRole.ADMIN, UserRole.ANALYST)"""
    async def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_user
    return dependency


def require_subscription(*tiers: SubscriptionTier):
    """Factory: require_subscription(SubscriptionTier.PRO)"""
    async def dependency(current_user: User = Depends(get_current_user)) -> User:
        # ENTERPRISE includes all PRO features, so also allow higher tiers
        tier_order = [SubscriptionTier.FREE, SubscriptionTier.PRO, SubscriptionTier.ENTERPRISE]
        user_tier_idx = tier_order.index(current_user.subscription_tier)
        min_required_idx = min(tier_order.index(t) for t in tiers)
        if user_tier_idx < min_required_idx:
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
