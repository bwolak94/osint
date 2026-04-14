"""Email value object with validation."""

import re
from dataclasses import dataclass

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


@dataclass(frozen=True)
class Email:
    """Immutable email value object."""

    address: str

    def __post_init__(self) -> None:
        if not EMAIL_REGEX.match(self.address):
            raise ValueError(f"Invalid email address: {self.address}")

    def __str__(self) -> str:
        return self.address

    @property
    def domain(self) -> str:
        """Return the domain part of the email."""
        return self.address.split("@")[1]

    @property
    def local_part(self) -> str:
        """Return the local part (before @) of the email."""
        return self.address.split("@")[0]
