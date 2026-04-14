"""Phone value object with basic validation."""

import re
from dataclasses import dataclass

# Accepts formats like +1234567890, 123-456-7890, (123) 456-7890, etc.
PHONE_REGEX = re.compile(r"^\+?[\d\s\-\(\)]{7,20}$")


@dataclass(frozen=True)
class Phone:
    """Immutable phone number value object."""

    number: str

    def __post_init__(self) -> None:
        if not PHONE_REGEX.match(self.number):
            raise ValueError(f"Invalid phone number: {self.number}")

    def __str__(self) -> str:
        return self.number

    @property
    def digits_only(self) -> str:
        """Return only the digit characters from the phone number."""
        return re.sub(r"\D", "", self.number)
