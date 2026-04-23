"""Cognitive load model — rule-based time slot scoring for the calendar agent.

Phase 2: deterministic rules based on time-of-day and day-of-week.
Phase 3: replace with ML model trained on productivity_events telemetry.

Peak focus windows (score ≥ 0.8):
  - 09:00–11:00  (morning deep work)
  - 14:00–16:00  (post-lunch focus recovery)

Day-of-week modifier:
  - Monday / Tuesday:   +0.1  (high-energy start of week)
  - Wednesday:           0.0  (neutral)
  - Thursday / Friday:  −0.1  (end-of-week fatigue)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TypedDict


class TimeSlot(TypedDict):
    """A calendar time slot with a cognitive load score."""

    start: str   # ISO 8601 datetime
    end: str     # ISO 8601 datetime
    score: float  # 0.0–1.0 (1.0 = peak focus)


# Time-of-day base scores: hour → base_score
_HOUR_BASE_SCORES: dict[int, float] = {
    0: 0.1, 1: 0.1, 2: 0.1, 3: 0.1, 4: 0.1, 5: 0.2,
    6: 0.3, 7: 0.4, 8: 0.6, 9: 0.9, 10: 0.95, 11: 0.85,
    12: 0.5, 13: 0.55, 14: 0.85, 15: 0.9, 16: 0.8, 17: 0.65,
    18: 0.5, 19: 0.4, 20: 0.3, 21: 0.2, 22: 0.15, 23: 0.1,
}

# Day-of-week modifier (Monday=0, Sunday=6)
_DOW_MODIFIER: dict[int, float] = {
    0: 0.1,   # Monday
    1: 0.1,   # Tuesday
    2: 0.0,   # Wednesday
    3: -0.1,  # Thursday
    4: -0.1,  # Friday
    5: -0.2,  # Saturday
    6: -0.2,  # Sunday
}


class CognitiveLoadModel:
    """Rule-based cognitive load scorer.

    Scores time slots based on:
    - Time of day (peak: 9–11 am, 14–16 pm)
    - Day of week (Mon/Tue higher than Thu/Fri)
    """

    async def score_slot(self, dt_iso: str) -> float:
        """Return a cognitive load score (0.0–1.0) for a given ISO datetime string."""
        try:
            dt = datetime.fromisoformat(dt_iso)
        except ValueError:
            return 0.0

        hour = dt.hour
        dow = dt.weekday()

        base = _HOUR_BASE_SCORES.get(hour, 0.3)
        modifier = _DOW_MODIFIER.get(dow, 0.0)
        score = max(0.0, min(1.0, base + modifier))
        return round(score, 4)

    async def find_best_slots(
        self,
        duration_minutes: int,
        n: int = 3,
    ) -> list[TimeSlot]:
        """Return the top n time slots in the next 7 days sorted by score descending.

        Args:
            duration_minutes: Duration of the slot in minutes.
            n:                Number of slots to return.

        Returns:
            List of TimeSlot TypedDicts sorted by score descending.
        """
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        candidates: list[TimeSlot] = []

        for day_offset in range(7):
            for hour in range(24):
                slot_start = now + timedelta(days=day_offset, hours=hour)
                if slot_start <= now:
                    continue  # skip past slots

                score = await self.score_slot(slot_start.isoformat())
                slot_end = slot_start + timedelta(minutes=duration_minutes)
                candidates.append(
                    TimeSlot(
                        start=slot_start.isoformat(),
                        end=slot_end.isoformat(),
                        score=score,
                    )
                )

        # Sort by score descending and return top n
        candidates.sort(key=lambda s: s["score"], reverse=True)
        return candidates[:n]
