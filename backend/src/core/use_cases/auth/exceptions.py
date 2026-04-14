"""Custom exceptions for authentication use cases."""


class AuthenticationError(Exception):
    """Raised when credentials are invalid."""
    pass


class AccountLockedError(Exception):
    """Raised when account is locked due to brute force."""
    pass


class TokenError(Exception):
    """Raised when a token is invalid, expired, or revoked."""
    pass


class SecurityAlert(Exception):
    """Raised when refresh token reuse is detected."""
    pass
