"""Investigation entity — a container for an OSINT research case."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from uuid import UUID

from src.core.domain.entities.types import InvestigationStatus, SeedInput
from src.core.domain.entities.user import User, UserRole


@dataclass
class Investigation:
    """Mutable entity representing an OSINT investigation case."""

    id: UUID
    owner_id: UUID
    title: str
    description: str
    status: InvestigationStatus
    seed_inputs: list[SeedInput]
    tags: frozenset[str]
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None

    # -- behaviour ----------------------------------------------------------

    def add_seed(self, seed: SeedInput) -> Investigation:
        """Append a seed input. Raises ValueError if the investigation is currently running."""
        if self.status is InvestigationStatus.RUNNING:
            raise ValueError("Cannot add seeds while the investigation is running.")
        return replace(self, seed_inputs=[*self.seed_inputs, seed])

    def mark_running(self) -> Investigation:
        """Transition to RUNNING. Only valid from DRAFT or PAUSED."""
        if self.status not in {InvestigationStatus.DRAFT, InvestigationStatus.PAUSED}:
            raise ValueError(
                f"Cannot start investigation from status {self.status.value!r}."
            )
        now = datetime.now(timezone.utc)
        return replace(self, status=InvestigationStatus.RUNNING, updated_at=now)

    def complete(self) -> Investigation:
        """Mark the investigation as completed."""
        now = datetime.now(timezone.utc)
        return replace(
            self,
            status=InvestigationStatus.COMPLETED,
            completed_at=now,
            updated_at=now,
        )

    def pause(self) -> Investigation:
        """Pause a running investigation."""
        if self.status is not InvestigationStatus.RUNNING:
            raise ValueError("Only a running investigation can be paused.")
        return replace(
            self,
            status=InvestigationStatus.PAUSED,
            updated_at=datetime.now(timezone.utc),
        )

    def archive(self) -> Investigation:
        """Archive a completed investigation."""
        if self.status is not InvestigationStatus.COMPLETED:
            raise ValueError("Only a completed investigation can be archived.")
        return replace(
            self,
            status=InvestigationStatus.ARCHIVED,
            updated_at=datetime.now(timezone.utc),
        )

    def can_be_deleted_by(self, user: User) -> bool:
        """The owner or an admin can delete, but only when in DRAFT or ARCHIVED status."""
        if self.status not in {
            InvestigationStatus.DRAFT,
            InvestigationStatus.ARCHIVED,
        }:
            return False
        return user.id == self.owner_id or user.role is UserRole.ADMIN
