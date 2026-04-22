"""Abstract base class for all RAG knowledge base ingestors."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RawDocument:
    """A single document fetched from an external source before chunking."""

    source: str
    source_id: str
    content: str
    metadata: dict = field(default_factory=dict)
    tenant_id: Optional[str] = None


class BaseIngestor(ABC):
    """Contract that every RAG source ingestor must satisfy."""

    @abstractmethod
    async def fetch(self) -> list[RawDocument]:
        """Fetch raw documents from the upstream source."""
        ...

    @abstractmethod
    def should_skip(self, doc: RawDocument) -> bool:
        """Return True if this document is already ingested and unchanged.

        Implementations may check a local cache, a DB timestamp, or an etag.
        Return False to always upsert (safe default).
        """
        ...
