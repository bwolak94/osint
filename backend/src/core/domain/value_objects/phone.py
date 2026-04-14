"""Phone number value object in E.164 format."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PhoneNumber:
    """Immutable, self-validating phone number value object (E.164)."""

    value: str
    country_code: str

    def __post_init__(self) -> None:
        normalized = self.value.strip()
        object.__setattr__(self, "value", normalized)
        object.__setattr__(self, "country_code", self.country_code.strip().upper())

        if not normalized.startswith("+"):
            raise ValueError(
                f"Phone number must start with '+' (E.164 format): {normalized!r}"
            )

        digits = normalized[1:]
        if not digits.isdigit():
            raise ValueError(
                f"Phone number must contain only digits after '+': {normalized!r}"
            )

        if not (7 <= len(digits) <= 15):
            raise ValueError(
                f"Phone number digit length must be between 7 and 15, "
                f"got {len(digits)}: {normalized!r}"
            )

    def region(self) -> str:
        """Return the ISO country code for this phone number."""
        return self.country_code

    def __str__(self) -> str:
        return self.value
