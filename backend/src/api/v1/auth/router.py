from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status


from src.adapters.auth.token_service import JWTTokenService
from src.adapters.cache.token_blacklist import RedisTokenBlacklist
from src.adapters.db.refresh_token_repository import SqlAlchemyRefreshTokenRepository
from src.adapters.db.repositories import SqlAlchemyUserRepository
from src.api.v1.auth.dependencies import (
    get_current_user,
    get_password_hasher,
    get_redis,
    get_refresh_token_repo,
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
from src.config import get_settings
from src.adapters.events.redis_publisher import RedisEventPublisher
from src.core.ports.event_publisher import IEventPublisher, noop_publisher
from src.core.use_cases.auth.change_password import ChangePasswordCommand, ChangePasswordUseCase
from src.core.use_cases.auth.exceptions import AccountLockedError, AuthenticationError, SecurityAlert, TokenError
from src.core.use_cases.auth.login import LoginCommand, LoginUseCase
from src.core.use_cases.auth.logout import LogoutCommand, LogoutUseCase
from src.core.use_cases.auth.refresh import RefreshCommand, RefreshTokenUseCase
from src.core.use_cases.auth.register import RegisterCommand, RegisterUserUseCase

router = APIRouter()

_COOKIE_MAX_AGE: int = 7 * 24 * 60 * 60  # 7 days in seconds


def _get_event_publisher(request: Request) -> IEventPublisher:
    """Return a Redis-backed publisher when Redis is available, otherwise no-op."""
    redis = getattr(request.app.state, "redis", None)
    return RedisEventPublisher(redis) if redis else noop_publisher


def _get_client_ip(request: Request) -> str | None:
    """Extract the real client IP, honouring X-Forwarded-For set by nginx.

    Takes the first (leftmost) address in X-Forwarded-For which is the original
    client IP as appended by nginx via proxy_add_x_forwarded_for.  Falls back to
    the direct connection host when the header is absent.
    """
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else None


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=str(user.email),
        role=user.role.value,
        subscription_tier=user.subscription_tier.value,
        is_active=user.is_active,
        is_email_verified=user.is_email_verified,
        created_at=user.created_at,
        tos_accepted_at=user.tos_accepted_at,
    )


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    # get_settings() is @lru_cache so this is effectively free on the hot path.
    secure = not get_settings().debug
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=secure,
        samesite="lax",  # "lax" allows cookie on top-level navigations; "strict" can block it
        max_age=_COOKIE_MAX_AGE,
        path="/api/v1/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key="refresh_token", path="/api/v1/auth")


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    user_repo: Annotated[SqlAlchemyUserRepository, Depends(get_user_repo)],
    token_service: Annotated[JWTTokenService, Depends(get_token_service)],
    password_hasher=Depends(get_password_hasher),
):
    use_case = RegisterUserUseCase(
        user_repo=user_repo,
        token_service=token_service,
        password_hasher=password_hasher,
        event_publisher=_get_event_publisher(request),
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
    password_hasher=Depends(get_password_hasher),
):
    use_case = LoginUseCase(
        user_repo=user_repo,
        token_service=token_service,
        refresh_token_repo=refresh_repo,
        password_hasher=password_hasher,
        event_publisher=_get_event_publisher(request),
    )

    ip = _get_client_ip(request)
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

    _set_refresh_cookie(response, result.tokens.refresh_token)
    return LoginResponse(
        access_token=result.tokens.access_token,
        user=_user_response(result.user),
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
        event_publisher=_get_event_publisher(request),
    )

    ip = _get_client_ip(request)
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
    access_token = auth.removeprefix("Bearer ") if auth.startswith("Bearer ") else ""

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
):
    # tos_accepted_at is now part of the User entity and populated by the repository.
    return _user_response(current_user)


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    user_repo: Annotated[SqlAlchemyUserRepository, Depends(get_user_repo)],
    refresh_repo: Annotated[SqlAlchemyRefreshTokenRepository, Depends(get_refresh_token_repo)],
    password_hasher=Depends(get_password_hasher),
):
    use_case = ChangePasswordUseCase(
        user_repo=user_repo,
        password_hasher=password_hasher,
        refresh_token_repo=refresh_repo,
        event_publisher=_get_event_publisher(request),
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
    # NOT YET IMPLEMENTED — returns 501 so callers know this is not functional.
    # Implement token validation + password update before enabling.
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Password reset is not yet implemented",
    )
