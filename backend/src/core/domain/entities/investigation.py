"""Investigation domain entity."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4


class InvestigationStatus(StrEnum):
    """Possible states of an investigation."""

    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


@dataclass
class Investigation:
    """Core domain entity representing an OSINT investigation."""

    title: str
    description: str
    owner_id: UUID
    id: UUID = field(default_factory=uuid4)
    status: InvestigationStatus = InvestigationStatus.DRAFT
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
