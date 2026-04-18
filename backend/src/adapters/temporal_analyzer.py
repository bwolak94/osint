"""Temporal Analyzer — temporal pattern analysis over OSINT scan results.

Reveals operational patterns by examining *when* entities appear together
across scan runs:

  - **Co-occurrence analysis** — which pairs of entities appear in scans
    taken within the same time window, and how often.
  - **Activity heatmap** — entity mention counts bucketed by hour.
  - **Periodicity detection** — does a given entity appear on a regular
    schedule?  Uses auto-correlation on the inter-arrival time series.

All methods are synchronous because they perform only in-memory computation.
Wrap calls in ``asyncio.get_event_loop().run_in_executor(None, ...)`` if
calling from an async context with large datasets.

Usage::

    analyzer = TemporalAnalyzer()

    patterns = analyzer.analyze_co_occurrence(scan_results, window_hours=6)
    for p in patterns[:5]:
        print(p.entity_a, p.entity_b, p.correlation_score)

    heatmap = analyzer.build_heatmap(scan_results, bucket_hours=1)

    info = analyzer.detect_periodic_activity("8.8.8.8", timestamps)
    print(info["period_hours"], info["confidence"])
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog

log = structlog.get_logger()

# ISO-8601 formats tried when parsing timestamps.
_DATETIME_FORMATS = (
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class TemporalPattern:
    """Co-occurrence relationship between two entities over time.

    Attributes:
        entity_a:           First entity value (e.g. "8.8.8.8").
        entity_b:           Second entity value (e.g. "example.com").
        co_occurrence_count: Number of time windows in which both appeared.
        time_windows:       ISO timestamp strings of those windows' start times.
        correlation_score:  Normalised Jaccard similarity of their window sets
                            (0.0 = never together, 1.0 = always together).
    """

    entity_a: str
    entity_b: str
    co_occurrence_count: int
    time_windows: list[str] = field(default_factory=list)
    correlation_score: float = 0.0


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------


class TemporalAnalyzer:
    """Analyses temporal patterns in OSINT scan result collections."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_co_occurrence(
        self,
        scan_results: list[dict[str, Any]],
        window_hours: int = 6,
    ) -> list[TemporalPattern]:
        """Identify pairs of entities that frequently appear in the same time window.

        Args:
            scan_results:  List of scan result dicts.  Each should contain:
                           - ``created_at``: ISO timestamp string.
                           - ``extracted_identifiers``: list of entity strings.
                           (Other keys such as ``scanner_name`` and
                           ``input_value`` are accepted but not required.)
            window_hours:  Size of the co-occurrence window in hours.

        Returns:
            List of :class:`TemporalPattern` objects sorted by
            ``correlation_score`` descending.  Returns empty list on failure.
        """
        if not scan_results:
            return []

        try:
            window_td = timedelta(hours=window_hours)

            # Build {window_bucket → set of entities} mapping.
            window_entities: dict[str, set[str]] = defaultdict(set)
            for result in scan_results:
                ts = self._parse_timestamp(result.get("created_at", ""))
                if ts is None:
                    continue
                bucket = self._floor_to_window(ts, window_hours).isoformat()
                identifiers = result.get("extracted_identifiers", [])
                # Also include the input value itself as an entity.
                input_value = result.get("input_value", "")
                if input_value:
                    identifiers = list(identifiers) + [input_value]
                for ident in identifiers:
                    if ident:
                        window_entities[bucket].add(str(ident))

            # Build {entity → set of windows} index.
            entity_windows: dict[str, set[str]] = defaultdict(set)
            for bucket, entities in window_entities.items():
                for entity in entities:
                    entity_windows[entity].add(bucket)

            entities_list = sorted(entity_windows.keys())
            patterns: list[TemporalPattern] = []

            for i, ea in enumerate(entities_list):
                for eb in entities_list[i + 1:]:
                    windows_a = entity_windows[ea]
                    windows_b = entity_windows[eb]
                    shared = windows_a & windows_b
                    if not shared:
                        continue
                    union = windows_a | windows_b
                    jaccard = len(shared) / len(union) if union else 0.0
                    patterns.append(
                        TemporalPattern(
                            entity_a=ea,
                            entity_b=eb,
                            co_occurrence_count=len(shared),
                            time_windows=sorted(shared),
                            correlation_score=round(jaccard, 4),
                        )
                    )

            patterns.sort(key=lambda p: p.correlation_score, reverse=True)
            log.info(
                "Co-occurrence analysis complete",
                patterns=len(patterns),
                windows=len(window_entities),
                window_hours=window_hours,
            )
            return patterns

        except Exception as exc:
            log.error("Co-occurrence analysis failed", error=str(exc), exc_info=True)
            return []

    def build_heatmap(
        self,
        scan_results: list[dict[str, Any]],
        bucket_hours: int = 1,
    ) -> dict[str, dict[str, int]]:
        """Build an entity-activity heatmap bucketed by time.

        Args:
            scan_results: Same format as :meth:`analyze_co_occurrence`.
            bucket_hours: Bucket granularity in hours (default 1).

        Returns:
            ``{hour_bucket_iso: {entity: occurrence_count}}``
            Returns empty dict on failure.
        """
        if not scan_results:
            return {}

        try:
            heatmap: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

            for result in scan_results:
                ts = self._parse_timestamp(result.get("created_at", ""))
                if ts is None:
                    continue
                bucket = self._floor_to_window(ts, bucket_hours).isoformat()
                identifiers: list[str] = list(result.get("extracted_identifiers", []))
                input_value = result.get("input_value", "")
                if input_value:
                    identifiers.append(input_value)
                for ident in identifiers:
                    if ident:
                        heatmap[bucket][str(ident)] += 1

            # Convert defaultdicts to plain dicts for clean serialisation.
            return {bucket: dict(counts) for bucket, counts in heatmap.items()}

        except Exception as exc:
            log.error("Heatmap build failed", error=str(exc), exc_info=True)
            return {}

    def detect_periodic_activity(
        self,
        entity: str,
        timestamps: list[str],
    ) -> dict[str, Any]:
        """Detect whether an entity appears on a regular schedule.

        Uses inter-arrival time auto-correlation to estimate the dominant
        period.  A simple approach:

          1. Parse and sort timestamps.
          2. Compute inter-arrival deltas in hours.
          3. Try candidate periods (1, 2, 4, 6, 8, 12, 24, 48, 72, 168 h).
          4. For each candidate, compute the fraction of deltas that are
             within ±20 % of a multiple of the candidate period.
          5. Return the candidate with the highest fraction as confidence.

        Args:
            entity:     The entity string being analysed (used for logging).
            timestamps: List of ISO timestamp strings when the entity was seen.

        Returns:
            Dict with keys:
              - ``period_hours``   (float | None) — dominant period, or None.
              - ``confidence``     (float) — fraction of deltas consistent
                                   with the period (0.0–1.0).
              - ``next_expected``  (str | None) — ISO timestamp of the next
                                   expected occurrence, or None.
              - ``observation_count`` (int) — number of valid timestamps used.
            Returns a safe default dict on failure.
        """
        default: dict[str, Any] = {
            "period_hours": None,
            "confidence": 0.0,
            "next_expected": None,
            "observation_count": 0,
        }

        if len(timestamps) < 3:
            return default

        try:
            parsed = sorted(filter(None, (self._parse_timestamp(t) for t in timestamps)))
            if len(parsed) < 3:
                return default

            deltas_hours = [
                (parsed[i + 1] - parsed[i]).total_seconds() / 3600.0
                for i in range(len(parsed) - 1)
            ]

            candidate_periods = [1, 2, 4, 6, 8, 12, 24, 48, 72, 168]
            best_period: float | None = None
            best_confidence = 0.0
            tolerance = 0.20  # ±20 % of the period

            for period in candidate_periods:
                consistent = sum(
                    1
                    for delta in deltas_hours
                    if self._is_near_multiple(delta, period, tolerance)
                )
                confidence = consistent / len(deltas_hours)
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_period = float(period)

            next_expected: str | None = None
            if best_period is not None and best_confidence >= 0.5:
                last_seen = parsed[-1]
                next_dt = last_seen + timedelta(hours=best_period)
                next_expected = next_dt.isoformat()

            log.debug(
                "Periodic activity detection",
                entity=entity,
                observations=len(parsed),
                period_hours=best_period,
                confidence=round(best_confidence, 3),
            )

            return {
                "period_hours": best_period if best_confidence >= 0.5 else None,
                "confidence": round(best_confidence, 4),
                "next_expected": next_expected,
                "observation_count": len(parsed),
            }

        except Exception as exc:
            log.error(
                "Periodic activity detection failed",
                entity=entity,
                error=str(exc),
                exc_info=True,
            )
            return default

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_timestamp(value: str) -> datetime | None:
        """Attempt to parse an ISO-ish timestamp string into a timezone-aware datetime."""
        if not value:
            return None
        for fmt in _DATETIME_FORMATS:
            try:
                dt = datetime.strptime(value, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue
        log.debug("Could not parse timestamp", value=value)
        return None

    @staticmethod
    def _floor_to_window(dt: datetime, window_hours: int) -> datetime:
        """Floor a datetime to the nearest window boundary."""
        total_seconds = int(dt.timestamp())
        window_seconds = window_hours * 3600
        floored_seconds = (total_seconds // window_seconds) * window_seconds
        return datetime.fromtimestamp(floored_seconds, tz=timezone.utc)

    @staticmethod
    def _is_near_multiple(value: float, period: float, tolerance: float) -> bool:
        """Return True if *value* is within *tolerance* of any integer multiple of *period*."""
        if period <= 0 or value <= 0:
            return False
        ratio = value / period
        nearest_multiple = round(ratio)
        if nearest_multiple == 0:
            return False
        return abs(ratio - nearest_multiple) / nearest_multiple <= tolerance
