"""Confidence score value object for OSINT data quality."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ConfidenceScore:
    """Immutable confidence score in the range [0.0, 1.0]."""

    value: float

    def __post_init__(self) -> None:
        if not (0.0 <= self.value <= 1.0):
            raise ValueError(
                f"Confidence score must be between 0.0 and 1.0, got {self.value}"
            )

    def level(self) -> Literal["low", "medium", "high", "certain"]:
        """Categorise the score into a human-readable confidence level."""
        if self.value < 0.3:
            return "low"
        if self.value < 0.6:
            return "medium"
        if self.value < 0.95:
            return "high"
        return "certain"

    def __add__(self, other: ConfidenceScore) -> ConfidenceScore:
        if not isinstance(other, ConfidenceScore):
            return NotImplemented
        return ConfidenceScore(min(self.value + other.value, 1.0))

    def __float__(self) -> float:
        return self.value

    def __lt__(self, other: ConfidenceScore) -> bool:
        if not isinstance(other, ConfidenceScore):
            return NotImplemented
        return self.value < other.value

    def __le__(self, other: ConfidenceScore) -> bool:
        if not isinstance(other, ConfidenceScore):
            return NotImplemented
        return self.value <= other.value

    def __gt__(self, other: ConfidenceScore) -> bool:
        if not isinstance(other, ConfidenceScore):
            return NotImplemented
        return self.value > other.value

    def __ge__(self, other: ConfidenceScore) -> bool:
        if not isinstance(other, ConfidenceScore):
            return NotImplemented
        return self.value >= other.value
