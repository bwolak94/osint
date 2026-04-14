"""Polish NIP (tax identification number) value object."""

from dataclasses import dataclass

# Weights used in the NIP modulo-11 checksum algorithm
_NIP_WEIGHTS: tuple[int, ...] = (6, 5, 7, 2, 3, 4, 5, 6, 7)


@dataclass(frozen=True)
class NIP:
    """Immutable, self-validating Polish NIP value object."""

    value: str

    def __post_init__(self) -> None:
        # Strip dashes and whitespace
        cleaned = self.value.replace("-", "").replace(" ", "").strip()
        object.__setattr__(self, "value", cleaned)

        if len(self.value) != 10:
            raise ValueError(
                f"NIP must be exactly 10 digits, got {len(self.value)}: {self.value!r}"
            )

        if not self.value.isdigit():
            raise ValueError(f"NIP must contain only digits: {self.value!r}")

        # Modulo 11 checksum validation
        digits = [int(d) for d in self.value]
        checksum = sum(d * w for d, w in zip(digits[:9], _NIP_WEIGHTS)) % 11

        if checksum == 10:
            raise ValueError(f"Invalid NIP checksum (remainder is 10): {self.value!r}")

        if checksum != digits[9]:
            raise ValueError(
                f"Invalid NIP checksum: expected {checksum}, "
                f"got {digits[9]}: {self.value!r}"
            )

    def formatted(self) -> str:
        """Return the NIP in the standard XXX-XXX-XX-XX format."""
        v = self.value
        return f"{v[:3]}-{v[3:6]}-{v[6:8]}-{v[8:10]}"

    def __str__(self) -> str:
        return self.value
