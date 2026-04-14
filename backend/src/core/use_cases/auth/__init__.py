"""Auth use cases for the OSINT platform."""

from src.core.use_cases.auth.register import RegisterUserUseCase, RegisterCommand, RegisterResult
from src.core.use_cases.auth.login import LoginUseCase, LoginCommand, LoginResult
from src.core.use_cases.auth.refresh import RefreshTokenUseCase, RefreshCommand, RefreshResult
from src.core.use_cases.auth.logout import LogoutUseCase, LogoutCommand
from src.core.use_cases.auth.change_password import ChangePasswordUseCase, ChangePasswordCommand
from src.core.use_cases.auth.exceptions import (
    AuthenticationError,
    AccountLockedError,
    TokenError,
    SecurityAlert,
)

__all__ = [
    "RegisterUserUseCase", "RegisterCommand", "RegisterResult",
    "LoginUseCase", "LoginCommand", "LoginResult",
    "RefreshTokenUseCase", "RefreshCommand", "RefreshResult",
    "LogoutUseCase", "LogoutCommand",
    "ChangePasswordUseCase", "ChangePasswordCommand",
    "AuthenticationError", "AccountLockedError", "TokenError", "SecurityAlert",
]
