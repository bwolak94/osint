"""Data retention policy engine for the OSINT platform."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Any

import structlog

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------


class RetentionAction(StrEnum):
    ARCHIVE = "archive"
    DELETE = "delete"


@dataclass
class RetentionPolicy:
    """Definition of a single retention rule."""

    id: str
    entity_type: str  # "investigation" | "scan_result" | "evidence"
    max_age_days: int
    action: RetentionAction
    workspace_id: str | None = None
    is_active: bool = True


@dataclass
class RetentionResult:
    """Outcome produced after evaluating a policy against a set of entities."""

    policy_id: str
    entity_type: str
    entities_affected: int
    action_taken: RetentionAction
    dry_run: bool
    errors: list[str]
    executed_at: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_timestamp(value: str | datetime) -> datetime:
    """Coerce *value* to a timezone-aware :class:`datetime`."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class RetentionPolicyEngine:
    """Evaluate retention policies and apply archive / delete actions."""

    def __init__(self, archive_client: Any | None = None) -> None:
        self._archive = archive_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate_policy(
        self,
        policy: RetentionPolicy,
        entities: list[dict],
        dry_run: bool = True,
    ) -> RetentionResult:
        """Apply *policy* to *entities* and return a structured result.

        When *dry_run* is ``True`` the engine only counts affected entities
        without performing any destructive operations.  Set it to ``False``
        to actually execute the configured :class:`RetentionAction`.
        """
        if not policy.is_active:
            log.info("retention.policy_skipped", policy_id=policy.id, reason="inactive")
            return RetentionResult(
                policy_id=policy.id,
                entity_type=policy.entity_type,
                entities_affected=0,
                action_taken=policy.action,
                dry_run=dry_run,
                errors=[],
                executed_at=_now_utc().isoformat(),
            )

        expired = self.find_expired(entities, policy.max_age_days)
        errors: list[str] = []

        if not dry_run:
            errors = self._apply_action(policy, expired)

        log.info(
            "retention.policy_evaluated",
            policy_id=policy.id,
            entity_type=policy.entity_type,
            expired_count=len(expired),
            action=policy.action,
            dry_run=dry_run,
        )

        return RetentionResult(
            policy_id=policy.id,
            entity_type=policy.entity_type,
            entities_affected=len(expired),
            action_taken=policy.action,
            dry_run=dry_run,
            errors=errors,
            executed_at=_now_utc().isoformat(),
        )

    def find_expired(self, entities: list[dict], max_age_days: int) -> list[dict]:
        """Return entities whose ``created_at`` is older than *max_age_days*."""
        cutoff = _now_utc() - timedelta(days=max_age_days)
        expired: list[dict] = []

        for entity in entities:
            raw_ts = entity.get("created_at")
            if raw_ts is None:
                log.warning("retention.missing_created_at", entity_id=entity.get("id"))
                continue
            try:
                created = _parse_timestamp(raw_ts)
            except (ValueError, TypeError) as exc:
                log.warning(
                    "retention.unparseable_timestamp",
                    entity_id=entity.get("id"),
                    raw=raw_ts,
                    error=str(exc),
                )
                continue

            if created < cutoff:
                expired.append(entity)

        return expired

    def compute_storage_stats(self, entities_by_type: dict[str, list[dict]]) -> dict:
        """Summarise storage usage metrics per entity type.

        Returns a mapping of::

            {
                entity_type: {
                    "count": int,
                    "oldest": ISO-8601 str | None,
                    "newest": ISO-8601 str | None,
                    "estimated_size_mb": float,
                }
            }

        The size estimate uses a rough heuristic of 5 KB per entity.
        """
        stats: dict[str, dict] = {}
        BYTES_PER_ENTITY = 5_120  # 5 KB heuristic

        for entity_type, entities in entities_by_type.items():
            timestamps: list[datetime] = []
            for e in entities:
                raw = e.get("created_at")
                if raw:
                    try:
                        timestamps.append(_parse_timestamp(raw))
                    except (ValueError, TypeError):
                        pass

            stats[entity_type] = {
                "count": len(entities),
                "oldest": min(timestamps).isoformat() if timestamps else None,
                "newest": max(timestamps).isoformat() if timestamps else None,
                "estimated_size_mb": round(
                    len(entities) * BYTES_PER_ENTITY / 1_048_576, 2
                ),
            }

        return stats

    def suggest_policies(self, stats: dict) -> list[dict]:
        """Propose sensible default retention policies based on observed stats.

        Rules applied:

        * ``scan_results`` > 10 000 entities → 90-day DELETE policy.
        * ``evidence`` > 5 000 entities → 180-day ARCHIVE policy.
        * Any type with oldest record > 365 days → 365-day ARCHIVE policy.
        * Otherwise a 730-day (2-year) ARCHIVE policy is suggested.
        """
        suggestions: list[dict] = []

        for entity_type, info in stats.items():
            count: int = info.get("count", 0)
            oldest_str: str | None = info.get("oldest")

            oldest_days: float | None = None
            if oldest_str:
                try:
                    oldest_dt = _parse_timestamp(oldest_str)
                    oldest_days = (_now_utc() - oldest_dt).days
                except (ValueError, TypeError):
                    pass

            if entity_type == "scan_results" and count > 10_000:
                suggestions.append(
                    {
                        "entity_type": entity_type,
                        "max_age_days": 90,
                        "action": RetentionAction.DELETE,
                        "reason": f"High volume ({count:,} records) — aggressive cleanup recommended.",
                    }
                )
            elif entity_type == "evidence" and count > 5_000:
                suggestions.append(
                    {
                        "entity_type": entity_type,
                        "max_age_days": 180,
                        "action": RetentionAction.ARCHIVE,
                        "reason": f"Large evidence store ({count:,} records) — archive older data.",
                    }
                )
            elif oldest_days is not None and oldest_days > 365:
                suggestions.append(
                    {
                        "entity_type": entity_type,
                        "max_age_days": 365,
                        "action": RetentionAction.ARCHIVE,
                        "reason": f"Oldest record is {oldest_days} days old — annual archival suggested.",
                    }
                )
            else:
                suggestions.append(
                    {
                        "entity_type": entity_type,
                        "max_age_days": 730,
                        "action": RetentionAction.ARCHIVE,
                        "reason": "Default 2-year retention policy.",
                    }
                )

        return suggestions

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _apply_action(
        self, policy: RetentionPolicy, expired: list[dict]
    ) -> list[str]:
        """Execute archive or delete on *expired* entities; return error messages."""
        errors: list[str] = []

        for entity in expired:
            entity_id = entity.get("id", "<unknown>")
            try:
                if policy.action == RetentionAction.ARCHIVE:
                    self._archive_entity(entity, policy)
                else:
                    self._delete_entity(entity, policy)
            except Exception as exc:  # noqa: BLE001
                msg = f"Failed to {policy.action} entity {entity_id}: {exc}"
                log.error("retention.action_failed", entity_id=entity_id, error=str(exc))
                errors.append(msg)

        return errors

    def _archive_entity(self, entity: dict, policy: RetentionPolicy) -> None:
        entity_id = entity.get("id", "<unknown>")
        if self._archive is not None:
            # Delegate to the injected archive client (S3, cold storage, etc.)
            self._archive.archive(entity, policy.entity_type)
        log.info(
            "retention.archived",
            entity_id=entity_id,
            entity_type=policy.entity_type,
            policy_id=policy.id,
        )

    def _delete_entity(self, entity: dict, policy: RetentionPolicy) -> None:
        entity_id = entity.get("id", "<unknown>")
        # In production this would call the DB session; here we log the intent.
        log.info(
            "retention.deleted",
            entity_id=entity_id,
            entity_type=policy.entity_type,
            policy_id=policy.id,
        )
