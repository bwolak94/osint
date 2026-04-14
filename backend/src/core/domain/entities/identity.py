"""Identity entity — an aggregated digital identity discovered during an investigation."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from src.core.domain.value_objects.confidence_score import ConfidenceScore
from src.core.domain.value_objects.email import Email
from src.core.domain.value_objects.nip import NIP
from src.core.domain.value_objects.phone import PhoneNumber
from src.core.domain.value_objects.url import URL


@dataclass
class Identity:
    """Mutable entity representing a consolidated digital identity."""

    id: UUID
    investigation_id: UUID
    display_name: str
    emails: frozenset[Email]
    phones: frozenset[PhoneNumber]
    usernames: frozenset[str]
    urls: frozenset[URL]
    nip: NIP | None
    confidence_score: ConfidenceScore
    sources: frozenset[str]
    metadata: dict[str, Any]
    created_at: datetime

    # -- behaviour ----------------------------------------------------------

    def merge_with(self, other: Identity) -> Identity:
        """Merge two identities into a new one, combining all collected data."""
        merged_metadata = {**self.metadata, **other.metadata}
        higher_confidence = max(self.confidence_score, other.confidence_score)

        return replace(
            self,
            id=uuid4(),
            emails=self.emails | other.emails,
            phones=self.phones | other.phones,
            usernames=self.usernames | other.usernames,
            urls=self.urls | other.urls,
            sources=self.sources | other.sources,
            confidence_score=higher_confidence,
            metadata=merged_metadata,
        )

    def add_email(self, email: Email, source: str) -> Identity:
        """Return a new instance with the given email and source added."""
        return replace(
            self,
            emails=self.emails | {email},
            sources=self.sources | {source},
        )

    def update_confidence(self, score: ConfidenceScore) -> Identity:
        """Return a new instance with an updated confidence score."""
        return replace(self, confidence_score=score)

    def is_same_as(self, other: Identity) -> bool:
        """Heuristic check: True if the identities share an email, or share a display name and at least one username."""
        if self.emails & other.emails:
            return True
        if self.display_name == other.display_name and (
            self.usernames & other.usernames
        ):
            return True
        return False
