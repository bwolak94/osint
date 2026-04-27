from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from src.dependencies import get_db as get_db_dep

from src.adapters.auth.token_service import JWTTokenService
from src.adapters.cache.token_blacklist import RedisTokenBlacklist
from src.adapters.db.refresh_token_repository import SqlAlchemyRefreshTokenRepository
from src.adapters.db.repositories import SqlAlchemyUserRepository
from src.api.v1.auth.dependencies import (
    get_current_user,
    get_password_hasher,
    get_redis,
    get_refresh_token_repo,
    get_token_blacklist,
    get_token_service,
    get_user_repo,
)
from src.api.v1.auth.schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    MessageResponse,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
)
from src.core.domain.entities.user import User
from src.core.use_cases.auth.change_password import ChangePasswordCommand, ChangePasswordUseCase
from src.core.use_cases.auth.exceptions import AccountLockedError, AuthenticationError, SecurityAlert, TokenError
from src.core.use_cases.auth.login import LoginCommand, LoginUseCase
from src.core.use_cases.auth.logout import LogoutCommand, LogoutUseCase
from src.core.use_cases.auth.refresh import RefreshCommand, RefreshTokenUseCase
from src.core.use_cases.auth.register import RegisterCommand, RegisterUserUseCase

router = APIRouter()


# Helper for a no-op event publisher (until real one is implemented)
class _NoOpEventPublisher:
    async def publish(self, event) -> None:
        pass

    async def publish_many(self, events) -> None:
        pass


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=str(user.email),
        role=user.role.value,
        subscription_tier=user.subscription_tier.value,
        is_active=user.is_active,
        is_email_verified=user.is_email_verified,
        created_at=user.created_at,
    )


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    from src.config import get_settings
    settings = get_settings()
    # In dev (debug=True) skip secure flag so the cookie works over plain HTTP
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=not settings.debug,
        samesite="lax",  # "lax" allows cookie on top-level navigations; "strict" can block it
        max_age=7 * 24 * 60 * 60,
        path="/api/v1/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key="refresh_token", path="/api/v1/auth")


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    response: Response,
    user_repo: Annotated[SqlAlchemyUserRepository, Depends(get_user_repo)],
    token_service: Annotated[JWTTokenService, Depends(get_token_service)],
    password_hasher=Depends(get_password_hasher),
):
    use_case = RegisterUserUseCase(
        user_repo=user_repo,
        token_service=token_service,
        password_hasher=password_hasher,
        event_publisher=_NoOpEventPublisher(),
    )
    try:
        result = await use_case.execute(RegisterCommand(email=body.email, password=body.password))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    _set_refresh_cookie(response, result.tokens.refresh_token)
    return RegisterResponse(
        user=_user_response(result.user),
        access_token=result.tokens.access_token,
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    user_repo: Annotated[SqlAlchemyUserRepository, Depends(get_user_repo)],
    token_service: Annotated[JWTTokenService, Depends(get_token_service)],
    refresh_repo: Annotated[SqlAlchemyRefreshTokenRepository, Depends(get_refresh_token_repo)],
    db: Annotated["AsyncSession", Depends(get_db_dep)],
    password_hasher=Depends(get_password_hasher),
):
    use_case = LoginUseCase(
        user_repo=user_repo,
        token_service=token_service,
        refresh_token_repo=refresh_repo,
        password_hasher=password_hasher,
        event_publisher=_NoOpEventPublisher(),
    )

    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")

    try:
        result = await use_case.execute(LoginCommand(
            email=body.email, password=body.password,
            ip_address=ip, user_agent=ua,
        ))
    except AuthenticationError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    except AccountLockedError:
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="Account temporarily locked")

    from sqlalchemy import select as _select
    from src.adapters.db.models import UserModel as _UserModel
    tos_at = await db.scalar(_select(_UserModel.tos_accepted_at).where(_UserModel.id == result.user.id))

    _set_refresh_cookie(response, result.tokens.refresh_token)
    user_resp = _user_response(result.user)
    user_resp.tos_accepted_at = tos_at
    return LoginResponse(
        access_token=result.tokens.access_token,
        user=user_resp,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    user_repo: Annotated[SqlAlchemyUserRepository, Depends(get_user_repo)],
    token_service: Annotated[JWTTokenService, Depends(get_token_service)],
    refresh_repo: Annotated[SqlAlchemyRefreshTokenRepository, Depends(get_refresh_token_repo)],
    refresh_token: str | None = Cookie(default=None),
):
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")

    use_case = RefreshTokenUseCase(
        user_repo=user_repo,
        token_service=token_service,
        refresh_token_repo=refresh_repo,
        event_publisher=_NoOpEventPublisher(),
    )

    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")

    try:
        result = await use_case.execute(RefreshCommand(
            refresh_token=refresh_token, ip_address=ip, user_agent=ua,
        ))
    except (TokenError, SecurityAlert) as e:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    _set_refresh_cookie(response, result.tokens.refresh_token)
    return TokenResponse(access_token=result.tokens.access_token)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    current_user: Annotated[User, Depends(get_current_user)],
    token_service: Annotated[JWTTokenService, Depends(get_token_service)],
    refresh_repo: Annotated[SqlAlchemyRefreshTokenRepository, Depends(get_refresh_token_repo)],
    refresh_token: str | None = Cookie(default=None),
):
    # Get access token from header
    auth = request.headers.get("authorization", "")
    access_token = auth.replace("Bearer ", "") if auth.startswith("Bearer ") else ""

    redis = getattr(request.app.state, "redis", None)
    blacklist = RedisTokenBlacklist(redis) if redis else None

    use_case = LogoutUseCase(
        token_service=token_service,
        token_blacklist=blacklist,
        refresh_token_repo=refresh_repo,
    )
    await use_case.execute(LogoutCommand(
        access_token=access_token, refresh_token=refresh_token,
    ))

    _clear_refresh_cookie(response)
    return MessageResponse(message="Successfully logged out")


@router.get("/me", response_model=UserResponse)
async def me(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated["AsyncSession", Depends(get_db_dep)],
):
    from sqlalchemy import select as _select
    from src.adapters.db.models import UserModel as _UserModel
    row = await db.scalar(_select(_UserModel.tos_accepted_at).where(_UserModel.id == current_user.id))
    resp = _user_response(current_user)
    resp.tos_accepted_at = row
    return resp


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    body: ChangePasswordRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    user_repo: Annotated[SqlAlchemyUserRepository, Depends(get_user_repo)],
    refresh_repo: Annotated[SqlAlchemyRefreshTokenRepository, Depends(get_refresh_token_repo)],
    password_hasher=Depends(get_password_hasher),
):
    use_case = ChangePasswordUseCase(
        user_repo=user_repo,
        password_hasher=password_hasher,
        refresh_token_repo=refresh_repo,
        event_publisher=_NoOpEventPublisher(),
    )
    try:
        await use_case.execute(ChangePasswordCommand(
            user_id=current_user.id,
            current_password=body.current_password,
            new_password=body.new_password,
        ))
    except AuthenticationError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    return MessageResponse(message="Password changed successfully")


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(body: ForgotPasswordRequest):
    # Placeholder: always return success to prevent email enumeration
    return MessageResponse(message="If an account with this email exists, a reset link has been sent")


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(body: ResetPasswordRequest):
    # Placeholder
    return MessageResponse(message="Password has been reset successfully")
