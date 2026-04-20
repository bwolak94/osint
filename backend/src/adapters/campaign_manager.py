"""Campaign Manager — business logic for grouping investigations into campaigns.

A *campaign* is a named collection of investigations that share common
entities (indicators, infrastructure, actors).  This module provides:

  - **Similarity-based grouping** — :meth:`CampaignManager.find_related_investigations`
    uses Jaccard similarity over extracted identifier sets to surface
    investigations that share significant entity overlap.

  - **Name suggestion** — :meth:`CampaignManager.suggest_campaign_name`
    analyses shared entities to produce a human-readable campaign label
    (e.g. "Campaign: .ru / ASN12345" or "Campaign: Domain Cluster").

  - **Summary building** — :meth:`CampaignManager.build_campaign_summary`
    aggregates metadata for a set of investigations into a
    :class:`CampaignSummary` dataclass ready for API serialisation.

Usage::

    manager = CampaignManager()

    # Find investigations similar to a given one.
    related = await manager.find_related_investigations(
        investigation_id="inv-001",
        all_identifiers={
            "inv-001": ["ip:1.2.3.4", "domain:evil.com"],
            "inv-002": ["ip:1.2.3.4", "domain:other.com"],
            "inv-003": ["domain:totally-different.org"],
        },
        threshold=0.3,
    )
    # related → [("inv-002", 0.5)]

    name = manager.suggest_campaign_name(investigations)
    summary = manager.build_campaign_summary("camp-001", name, investigations)
"""

from __future__ import annotations

import asyncio
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import structlog

log = structlog.get_logger()

# Prefix patterns used when parsing identifier strings ("prefix:value").
_IDENTIFIER_PREFIX_RE = re.compile(r"^([a-z_]+):(.+)$", re.I)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class CampaignSummary:
    """Aggregated metadata for a campaign.

    Attributes:
        id:                  Unique campaign identifier (UUID string).
        name:                Human-readable campaign name.
        description:         Free-text description.
        investigation_ids:   IDs of all member investigations.
        investigation_count: Convenience count of ``investigation_ids``.
        entity_overlap:      ``{entity_value: count}`` of entities that appear
                             in more than one investigation.
        first_seen:          ISO timestamp of the earliest investigation
                             creation date.
        last_activity:       ISO timestamp of the most recent activity.
        tags:                Analyst-assigned or auto-generated tags.
    """

    id: str
    name: str
    description: str
    investigation_ids: list[str]
    investigation_count: int
    entity_overlap: dict[str, int]
    first_seen: str
    last_activity: str
    tags: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Campaign manager
# ---------------------------------------------------------------------------


class CampaignManager:
    """Business logic for grouping investigations into threat campaigns.

    All public methods are async so they integrate cleanly into FastAPI route
    handlers, even though the current implementations are CPU-bound and do
    not perform I/O.  Heavy computation is offloaded to a thread executor.
    """

    async def find_related_investigations(
        self,
        investigation_id: str,
        all_identifiers: dict[str, list[str]],
        threshold: float = 0.3,
    ) -> list[tuple[str, float]]:
        """Find investigations similar to *investigation_id* by entity overlap.

        Similarity is computed as the Jaccard index between the identifier
        sets of the target investigation and every other investigation.

        Args:
            investigation_id: ID of the investigation to compare against.
            all_identifiers:  Mapping of ``investigation_id → [identifier, ...]``
                              where identifiers are strings like ``"ip:1.2.3.4"``
                              or plain entity values.
            threshold:        Minimum Jaccard similarity (inclusive) for an
                              investigation to be included in the result.

        Returns:
            List of ``(investigation_id, similarity_score)`` tuples, sorted by
            similarity descending.  The target investigation itself is excluded.
            Returns empty list on failure or if the target has no identifiers.
        """
        target_ids = all_identifiers.get(investigation_id)
        if not target_ids:
            log.warning(
                "find_related_investigations: target has no identifiers",
                investigation_id=investigation_id,
            )
            return []

        try:
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                self._compute_similarities,
                investigation_id,
                set(target_ids),
                all_identifiers,
                threshold,
            )
            log.info(
                "Related investigations found",
                target=investigation_id,
                related=len(results),
                threshold=threshold,
            )
            return results
        except Exception as exc:
            log.error(
                "find_related_investigations failed",
                error=str(exc),
                exc_info=True,
            )
            return []

    def _compute_similarities(
        self,
        target_id: str,
        target_set: set[str],
        all_identifiers: dict[str, list[str]],
        threshold: float,
    ) -> list[tuple[str, float]]:
        """Synchronous inner loop for Jaccard similarity computation."""
        results: list[tuple[str, float]] = []
        for inv_id, identifiers in all_identifiers.items():
            if inv_id == target_id:
                continue
            score = self.jaccard_similarity(target_set, set(identifiers))
            if score >= threshold:
                results.append((inv_id, round(score, 4)))
        results.sort(key=lambda t: t[1], reverse=True)
        return results

    def jaccard_similarity(self, set_a: set[str], set_b: set[str]) -> float:
        """Compute the Jaccard similarity coefficient between two string sets.

        J(A, B) = |A ∩ B| / |A ∪ B|

        Args:
            set_a: First identifier set.
            set_b: Second identifier set.

        Returns:
            Float in [0.0, 1.0].  Returns 0.0 if both sets are empty.
        """
        if not set_a and not set_b:
            return 0.0
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0

    def suggest_campaign_name(self, investigations: list[dict[str, Any]]) -> str:
        """Generate a descriptive campaign name from shared entity characteristics.

        Extraction priority:
          1. Common TLD (e.g. ``".ru"``) across domain entities.
          2. Common ASN across infrastructure entities.
          3. Most frequent entity type label.
          4. Fallback: ``"Campaign: Mixed Infrastructure"``.

        Args:
            investigations: List of investigation dicts.  Each should contain
                            an ``identifiers`` key with a list of entity
                            strings, and optionally ``properties`` dicts.

        Returns:
            A short, human-readable campaign name string.
        """
        if not investigations:
            return "Campaign: Unknown"

        all_identifiers: list[str] = []
        for inv in investigations:
            all_identifiers.extend(inv.get("identifiers", []))

        if not all_identifiers:
            return "Campaign: Mixed Infrastructure"

        # Collect TLDs from domain-like identifiers.
        tld_counter: Counter[str] = Counter()
        asn_counter: Counter[str] = Counter()
        prefix_counter: Counter[str] = Counter()

        for identifier in all_identifiers:
            parsed = _IDENTIFIER_PREFIX_RE.match(identifier)
            if parsed:
                prefix, value = parsed.group(1).lower(), parsed.group(2)
            else:
                prefix, value = "unknown", identifier

            prefix_counter[prefix] += 1

            if prefix in ("domain", "url", "subdomain"):
                tld = self._extract_tld(value)
                if tld:
                    tld_counter[tld] += 1

            if prefix == "asn":
                asn_counter[value] += 1

        # 1. Common TLD?
        if tld_counter:
            top_tld, top_tld_count = tld_counter.most_common(1)[0]
            if top_tld_count >= max(2, len(investigations) // 2):
                suffix = f" / ASN:{asn_counter.most_common(1)[0][0]}" if asn_counter else ""
                return f"Campaign: {top_tld}{suffix}"

        # 2. Common ASN?
        if asn_counter:
            top_asn, top_asn_count = asn_counter.most_common(1)[0]
            if top_asn_count >= max(2, len(investigations) // 2):
                return f"Campaign: ASN {top_asn}"

        # 3. Dominant entity type?
        if prefix_counter:
            top_prefix = prefix_counter.most_common(1)[0][0]
            label_map = {
                "ip": "IP Infrastructure",
                "domain": "Domain Cluster",
                "email": "Email Identity",
                "username": "Social Identity",
                "hash": "Malware Hash Cluster",
                "url": "URL Cluster",
                "phone": "Phone Cluster",
            }
            label = label_map.get(top_prefix, top_prefix.title())
            return f"Campaign: {label}"

        return "Campaign: Mixed Infrastructure"

    def build_campaign_summary(
        self,
        campaign_id: str | None,
        name: str,
        investigations: list[dict[str, Any]],
        description: str = "",
        tags: list[str] | None = None,
    ) -> CampaignSummary:
        """Build a :class:`CampaignSummary` from a list of investigation dicts.

        Args:
            campaign_id:    UUID string for the campaign.  Auto-generated if
                            None.
            name:           Campaign display name.
            investigations: List of investigation dicts, each containing at
                            minimum an ``id`` key.  Optional keys:
                            ``created_at`` (ISO string), ``updated_at`` (ISO
                            string), ``identifiers`` (list of entity strings).
            description:    Free-text campaign description.
            tags:           Optional list of tag strings.

        Returns:
            A populated :class:`CampaignSummary`.
        """
        if campaign_id is None:
            campaign_id = str(uuid4())

        investigation_ids: list[str] = [
            str(inv.get("id", "")) for inv in investigations if inv.get("id")
        ]

        # Compute entity overlap: count how many investigations each entity appears in.
        entity_inv_count: Counter[str] = Counter()
        for inv in investigations:
            identifiers = inv.get("identifiers", [])
            # De-duplicate within a single investigation before counting.
            for ident in set(identifiers):
                if ident:
                    entity_inv_count[ident] += 1

        # Only include entities that appear in more than one investigation.
        entity_overlap = {
            entity: count
            for entity, count in entity_inv_count.items()
            if count > 1
        }

        # Determine time bounds.
        timestamps: list[datetime] = []
        for inv in investigations:
            for key in ("created_at", "updated_at", "last_activity"):
                raw = inv.get(key, "")
                if raw:
                    dt = self._parse_iso(raw)
                    if dt:
                        timestamps.append(dt)

        now_iso = datetime.now(timezone.utc).isoformat()
        first_seen = min(timestamps).isoformat() if timestamps else now_iso
        last_activity = max(timestamps).isoformat() if timestamps else now_iso

        return CampaignSummary(
            id=campaign_id,
            name=name,
            description=description,
            investigation_ids=investigation_ids,
            investigation_count=len(investigation_ids),
            entity_overlap=entity_overlap,
            first_seen=first_seen,
            last_activity=last_activity,
            tags=list(tags or []),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_tld(value: str) -> str | None:
        """Extract the public TLD from a domain or URL string."""
        # Strip URL scheme.
        value = re.sub(r"^https?://", "", value).rstrip("/")
        # Strip path/port.
        value = value.split("/")[0].split(":")[0]
        parts = value.rsplit(".", 1)
        if len(parts) == 2 and parts[1]:
            return f".{parts[1]}"
        return None

    @staticmethod
    def _parse_iso(value: str) -> datetime | None:
        """Best-effort ISO timestamp parser; returns None on failure."""
        _FORMATS = (
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        )
        for fmt in _FORMATS:
            try:
                dt = datetime.strptime(value, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue
        return None
