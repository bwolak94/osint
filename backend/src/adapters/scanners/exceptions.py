"""Scanner-specific exceptions with typed error taxonomy."""
from __future__ import annotations


class ScannerError(Exception):
    """Base exception for all scanner errors."""


class ScannerUnavailableError(ScannerError):
    """Raised when scanner is unavailable (circuit breaker open)."""


class RateLimitError(ScannerError):
    """Raised when the external service returns 429.

    Attributes:
        retry_after: Optional number of seconds to wait before retrying,
            extracted from the Retry-After header when available.
    """

    def __init__(self, message: str = "", retry_after: int | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class ScanAuthError(ScannerError):
    """Raised when the scanner's API key is invalid or expired (401/403).

    This is a permanent failure — the circuit breaker should open immediately
    and an admin alert should be fired.
    """


class ScannerNotFoundError(ScannerError):
    """Raised when the target entity does not exist in the external service (404).

    This is *not* a failure — the scanner ran successfully but the target was
    absent.  The circuit breaker should NOT count this as a failure.
    """


class ScanTimeoutError(ScannerError):
    """Raised when a scan exceeds its timeout."""


class ScanParseError(ScannerError):
    """Raised when scanner output cannot be parsed."""


class ScannerQuotaExceededError(ScannerError):
    """Raised when the pre-scan quota check determines no budget remains.

    Unlike RateLimitError (which comes from the external API), this is raised
    *before* the external call is made so we never waste quota on a call that
    would be rejected anyway.

    Attributes:
        scanner_name: Name of the scanner whose quota is exhausted.
        resets_at: ISO-8601 timestamp at which the quota resets, if known.
    """

    def __init__(
        self,
        scanner_name: str,
        message: str = "",
        resets_at: str | None = None,
    ) -> None:
        super().__init__(message or f"Quota exhausted for scanner '{scanner_name}'")
        self.scanner_name = scanner_name
        self.resets_at = resets_at
