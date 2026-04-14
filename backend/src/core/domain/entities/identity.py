"""Identity domain entity."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class IdentityType(StrEnum):
    """Classification of an identity."""

    PERSON = "PERSON"
    ORGANIZATION = "ORGANIZATION"
    UNKNOWN = "UNKNOWN"


@dataclass
class Identity:
    """Represents a resolved or partially resolved identity in an investigation."""

    investigation_id: UUID
    label: str
    type: IdentityType = IdentityType.UNKNOWN
    id: UUID = field(default_factory=uuid4)
    metadata: dict[str, Any] = field(default_factory=dict)
