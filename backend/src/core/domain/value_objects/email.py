"""Email value object with self-validation."""

import re
from dataclasses import dataclass

# Simplified RFC 5322 pattern
_EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

_DISPOSABLE_DOMAINS: frozenset[str] = frozenset(
    {
        "mailinator.com",
        "guerrillamail.com",
        "tempmail.com",
        "throwaway.email",
        "yopmail.com",
        "sharklasers.com",
        "guerrillamailblock.com",
        "grr.la",
        "discard.email",
        "fakeinbox.com",
    }
)


@dataclass(frozen=True)
class Email:
    """Immutable, self-validating email value object."""

    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip().lower()
        object.__setattr__(self, "value", normalized)
        if not _EMAIL_REGEX.match(self.value):
            raise ValueError(f"Invalid email address: {self.value!r}")

    def domain(self) -> str:
        """Return the domain part of the email address."""
        return self.value.split("@", 1)[1]

    def is_disposable(self) -> bool:
        """Check whether the email belongs to a known disposable email provider."""
        return self.domain() in _DISPOSABLE_DOMAINS

    def __str__(self) -> str:
        return self.value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Email):
            return NotImplemented
        return self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)
