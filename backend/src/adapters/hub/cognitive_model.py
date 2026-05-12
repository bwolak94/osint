"""CognitiveLoadModel — rule-based (v1) + ML (v2) implementations.

The ML model uses scikit-learn RandomForestClassifier trained on productivity_events.
Falls back to rule-based if no model in cache or < 30 days data.

A/B switching: controlled by COGNITIVE_MODEL_VERSION env var ("rule_based" | "ml").
"""

from __future__ import annotations

import os
import pickle
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol, runtime_checkable

import structlog

log = structlog.get_logger(__name__)

_MODEL_CACHE_KEY = "cognitive_model:{user_id}"
_MODEL_VERSION_ENV = "COGNITIVE_MODEL_VERSION"

# Cognitive load scores by time-of-day bucket
_MORNING_SCORE = 0.85    # 9–11
_AFTERNOON_SCORE = 0.70  # 14–16
_EVENING_SCORE = 0.55    # 17–19
_LUNCH_SCORE = 0.30      # 12–13
_NIGHT_SCORE = 0.10      # all other hours
_WEEKEND_PENALTY = 0.20


def _hour_score(hour: int) -> float:
    """Return base cognitive load score for a given hour-of-day (0–23)."""
    if 9 <= hour <= 11:
        return _MORNING_SCORE
    if 14 <= hour <= 16:
        return _AFTERNOON_SCORE
    if 17 <= hour <= 19:
        return _EVENING_SCORE
    if 12 <= hour <= 13:
        return _LUNCH_SCORE
    return _NIGHT_SCORE


def _build_candidate_slots(duration_minutes: int, n: int) -> list[datetime]:
    """Generate candidate datetimes across the next 7 days at hourly granularity."""
    now = datetime.now(tz=timezone.utc)
    candidates: list[datetime] = []
    for day_offset in range(7):
        base = (now + timedelta(days=day_offset)).replace(
            minute=0, second=0, microsecond=0
        )
        for hour in range(24):
            slot_start = base.replace(hour=hour)
            if slot_start <= now:
                continue
            slot_end = slot_start + timedelta(minutes=duration_minutes)
            if slot_end.day != slot_start.day:
                # Slot crosses midnight — skip to keep things simple
                continue
            candidates.append(slot_start)
    return candidates


@runtime_checkable
class CognitiveLoadModel(Protocol):
    """Protocol defining the CognitiveLoadModel interface."""

    async def score_slot(self, dt: datetime) -> float:
        """Return a cognitive load score [0, 1] for the given datetime."""
        ...

    async def find_best_slots(
        self, duration_minutes: int, n: int = 3
    ) -> list[dict[str, Any]]:
        """Return the top-n slots across the next 7 days, sorted by score descending."""
        ...


class RuleBasedCognitiveModel:
    """Deterministic heuristic cognitive load scorer.

    Does not require any training data or external dependencies.
    """

    async def score_slot(self, dt: datetime) -> float:
        """Rule-based score for *dt*: combines hour-of-day and weekend penalty."""
        score = _hour_score(dt.hour)
        if dt.weekday() >= 5:  # Saturday=5, Sunday=6
            score = max(0.0, score - _WEEKEND_PENALTY)
        return round(score, 4)

    async def find_best_slots(
        self, duration_minutes: int, n: int = 3
    ) -> list[dict[str, Any]]:
        """Return top-n candidate slots from the next 7 days, ranked by score."""
        candidates = _build_candidate_slots(duration_minutes, n)
        scored: list[tuple[float, datetime]] = []
        for dt in candidates:
            s = await self.score_slot(dt)
            scored.append((s, dt))

        scored.sort(key=lambda t: t[0], reverse=True)
        top = scored[:n]

        return [
            {
                "start": dt.isoformat(),
                "end": (dt + timedelta(minutes=duration_minutes)).isoformat(),
                "score": score,
            }
            for score, dt in top
        ]


class MLCognitiveModel:
    """RandomForest-based cognitive load scorer.

    The trained model is persisted in Redis (key: ``cognitive_model:{user_id}``).
    Falls back transparently to :class:`RuleBasedCognitiveModel` when:
    - No serialised model exists in Redis.
    - Redis is unavailable.
    - Prediction raises any exception.
    """

    def __init__(
        self,
        user_id: str,
        redis_client: Any,
        db_session: Any | None = None,
    ) -> None:
        self._user_id = user_id
        self._redis = redis_client
        self._db_session = db_session
        self._fallback = RuleBasedCognitiveModel()
        self._cache_key = _MODEL_CACHE_KEY.format(user_id=user_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_features(self, dt: datetime) -> list[float]:
        """Extract feature vector from a datetime object."""
        hour_of_day = dt.hour
        day_of_week = dt.weekday()  # 0=Mon … 6=Sun
        is_weekend = 1.0 if dt.weekday() >= 5 else 0.0
        days_until_weekend = max(0, 4 - dt.weekday())  # 0 when already weekend
        return [float(hour_of_day), float(day_of_week), is_weekend, float(days_until_weekend)]

    async def _load_model(self) -> Any | None:
        """Load a pickled sklearn model from Redis. Returns None on any error."""
        try:
            if hasattr(self._redis, "get"):
                raw = self._redis.get(self._cache_key)
            else:
                raw = await self._redis.get(self._cache_key)

            if raw is None:
                return None

            if isinstance(raw, str):
                raw = raw.encode("latin-1")

            return pickle.loads(raw)  # noqa: S301
        except Exception as exc:
            await log.awarning(
                "ml_model_load_failed",
                user_id=self._user_id,
                error=str(exc),
            )
            return None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def score_slot(self, dt: datetime) -> float:
        """Predict cognitive load score for *dt* using the cached ML model."""
        model = await self._load_model()
        if model is None:
            return await self._fallback.score_slot(dt)

        try:
            features = self._extract_features(dt)
            proba = model.predict_proba([features])[0]
            # Class 1 probability ≈ likelihood of productive completion
            score = float(proba[1]) if len(proba) > 1 else float(proba[0])
            return round(score, 4)
        except Exception as exc:
            await log.awarning(
                "ml_model_predict_failed",
                user_id=self._user_id,
                error=str(exc),
            )
            return await self._fallback.score_slot(dt)

    async def find_best_slots(
        self, duration_minutes: int, n: int = 3
    ) -> list[dict[str, Any]]:
        """Return top-n candidate slots ranked by ML score, fallback to rule-based."""
        model = await self._load_model()
        if model is None:
            return await self._fallback.find_best_slots(duration_minutes, n)

        candidates = _build_candidate_slots(duration_minutes, n)
        scored: list[tuple[float, datetime]] = []
        for dt in candidates:
            try:
                features = self._extract_features(dt)
                proba = model.predict_proba([features])[0]
                score = float(proba[1]) if len(proba) > 1 else float(proba[0])
            except Exception:
                score = await self._fallback.score_slot(dt)
            scored.append((score, dt))

        scored.sort(key=lambda t: t[0], reverse=True)
        top = scored[:n]

        return [
            {
                "start": dt.isoformat(),
                "end": (dt + timedelta(minutes=duration_minutes)).isoformat(),
                "score": round(score, 4),
            }
            for score, dt in top
        ]


def get_cognitive_model(
    user_id: str,
    redis_client: Any,
    db_session: Any | None = None,
) -> CognitiveLoadModel:
    """Factory: returns MLCognitiveModel or RuleBasedCognitiveModel based on env var.

    The env var ``COGNITIVE_MODEL_VERSION`` controls which implementation is used:
    - ``"ml"``          → :class:`MLCognitiveModel`
    - ``"rule_based"``  → :class:`RuleBasedCognitiveModel` (default)
    """
    version = os.getenv(_MODEL_VERSION_ENV, "rule_based").strip().lower()
    if version == "ml":
        log.info("cognitive_model_factory", version="ml", user_id=user_id)
        return MLCognitiveModel(user_id=user_id, redis_client=redis_client, db_session=db_session)

    log.info("cognitive_model_factory", version="rule_based", user_id=user_id)
    return RuleBasedCognitiveModel()
