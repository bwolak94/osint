"""Simple entity resolution based on shared identifiers.

For production use with large datasets, this should be replaced with
Splink + DuckDB for probabilistic record linkage.
"""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

import structlog

log = structlog.get_logger()


@dataclass
class IdentityCluster:
    """A group of scan results that likely refer to the same real-world entity."""
    cluster_id: UUID = field(default_factory=uuid4)
    emails: set[str] = field(default_factory=set)
    usernames: set[str] = field(default_factory=set)
    phones: set[str] = field(default_factory=set)
    nips: set[str] = field(default_factory=set)
    services: set[str] = field(default_factory=set)
    urls: set[str] = field(default_factory=set)
    confidence: float = 0.0
    raw_records: list[dict[str, Any]] = field(default_factory=list)

    def overlaps_with(self, other: "IdentityCluster") -> bool:
        """Check if two clusters share any identifier."""
        return bool(
            self.emails & other.emails
            or self.usernames & other.usernames
            or self.phones & other.phones
            or self.nips & other.nips
        )

    def merge(self, other: "IdentityCluster") -> "IdentityCluster":
        """Merge another cluster into this one."""
        return IdentityCluster(
            cluster_id=self.cluster_id,
            emails=self.emails | other.emails,
            usernames=self.usernames | other.usernames,
            phones=self.phones | other.phones,
            nips=self.nips | other.nips,
            services=self.services | other.services,
            urls=self.urls | other.urls,
            confidence=max(self.confidence, other.confidence),
            raw_records=self.raw_records + other.raw_records,
        )


class SimpleEntityResolver:
    """Rule-based entity resolution using exact identifier matching.

    Groups scan results into clusters where any shared identifier
    (email, username, phone, NIP) causes a merge. Produces a
    confidence score based on the number of shared identifiers.
    """

    async def resolve(self, investigation_id: UUID) -> list[IdentityCluster]:
        """Resolve entities for an investigation.

        In production, this loads scan results from the DB. For now,
        returns an empty list as a placeholder.
        """
        log.info("Running entity resolution", investigation_id=str(investigation_id))
        # Placeholder — in production, load ScanResults from DB and cluster them
        return []

    def cluster_records(self, records: list[dict[str, Any]]) -> list[IdentityCluster]:
        """Cluster a list of raw scan records by shared identifiers."""
        clusters: list[IdentityCluster] = []

        for record in records:
            cluster = self._record_to_cluster(record)
            merged = False

            for i, existing in enumerate(clusters):
                if existing.overlaps_with(cluster):
                    clusters[i] = existing.merge(cluster)
                    merged = True
                    break

            if not merged:
                clusters.append(cluster)

        # Calculate confidence scores
        for cluster in clusters:
            identifier_count = (
                len(cluster.emails) + len(cluster.usernames)
                + len(cluster.phones) + len(cluster.nips)
            )
            cluster.confidence = min(1.0, identifier_count * 0.15)

        return clusters

    @staticmethod
    def _record_to_cluster(record: dict[str, Any]) -> IdentityCluster:
        cluster = IdentityCluster(raw_records=[record])
        for ident in record.get("extracted_identifiers", []):
            if ":" in ident:
                kind, value = ident.split(":", 1)
                if kind == "email":
                    cluster.emails.add(value)
                elif kind == "service":
                    cluster.services.add(value)
                elif kind == "url":
                    cluster.urls.add(value)
                elif kind == "phone":
                    cluster.phones.add(value)
                elif kind == "nip":
                    cluster.nips.add(value)
                elif kind == "username":
                    cluster.usernames.add(value)
        return cluster
