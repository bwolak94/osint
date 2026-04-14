"""Scanner-specific exceptions."""


class ScannerError(Exception):
    """Base exception for all scanner errors."""
    pass


class ScannerUnavailableError(ScannerError):
    """Raised when scanner is unavailable (circuit breaker open)."""
    pass


class RateLimitError(ScannerError):
    """Raised when the external service returns 429."""
    pass


class ScanTimeoutError(ScannerError):
    """Raised when a scan exceeds its timeout."""
    pass


class ScanParseError(ScannerError):
    """Raised when scanner output cannot be parsed."""
    pass
