"""Celery tasks for training and monitoring the cognitive load model.

Tasks run on the 'light' queue.
  - retrain_cognitive_model_task: weekly beat task; trains a RandomForest on
    productivity_events from the last 90 days and stores the model in Redis.
  - check_model_drift_task: evaluates accuracy on the last 7 days; if accuracy
    drops below 0.65 it reverts to the rule-based model by removing the Redis key.
"""

from __future__ import annotations

import os
import pickle
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog

from src.workers.celery_app import celery_app

log = structlog.get_logger(__name__)

_MODEL_CACHE_KEY = "cognitive_model:{user_id}"
_MODEL_TTL = 7 * 24 * 3600  # 7 days in seconds
_MIN_EVENTS_FOR_TRAINING = 30
_DRIFT_ACCURACY_THRESHOLD = 0.65
_COGNITIVE_MODEL_VERSION_ENV = "COGNITIVE_MODEL_VERSION"


def _get_redis_sync() -> Any:
    """Synchronous Redis client for Celery worker context."""
    from redis import Redis as SyncRedis

    from src.config import get_settings

    settings = get_settings()
    return SyncRedis.from_url(settings.redis_url, decode_responses=False)


def _get_db_url() -> str:
    from src.config import get_settings

    settings = get_settings()
    # Convert asyncpg URL to psycopg2-compatible sync URL for raw SQL via sqlalchemy sync
    return settings.postgres_dsn.replace("postgresql+asyncpg://", "postgresql://")


def _fetch_productivity_events(days: int) -> list[dict[str, Any]]:
    """Fetch productivity events from the last *days* days using a synchronous DB connection."""
    import sqlalchemy as sa

    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
    db_url = _get_db_url()

    engine = sa.create_engine(db_url, echo=False)
    with engine.connect() as conn:
        result = conn.execute(
            sa.text(
                """
                SELECT created_at, completed, deferred
                FROM productivity_events
                WHERE created_at >= :cutoff
                ORDER BY created_at ASC
                """
            ),
            {"cutoff": cutoff},
        )
        rows = result.mappings().all()

    engine.dispose()
    return [dict(row) for row in rows]


def _build_feature_matrix(
    events: list[dict[str, Any]],
) -> tuple[list[list[float]], list[int]]:
    """Build feature matrix and label vector from raw event rows."""
    X: list[list[float]] = []
    y: list[int] = []

    for event in events:
        created_at: datetime = event["created_at"]
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        hour_of_day = float(created_at.hour)
        day_of_week = float(created_at.weekday())
        is_weekend = 1.0 if created_at.weekday() >= 5 else 0.0
        days_until_weekend = float(max(0, 4 - created_at.weekday()))

        X.append([hour_of_day, day_of_week, is_weekend, days_until_weekend])

        # Label: 1 if the event was completed, 0 if deferred (or not completed)
        label = 1 if event.get("completed") and not event.get("deferred") else 0
        y.append(label)

    return X, y


def _log_model_version(user_id: str, version: str, accuracy: float | None = None) -> None:
    """Insert a row into hub_cognitive_model_log via synchronous SQL."""
    import sqlalchemy as sa

    db_url = _get_db_url()
    engine = sa.create_engine(db_url, echo=False)
    try:
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    """
                    INSERT INTO hub_cognitive_model_log
                        (user_id, model_version, accuracy, logged_at)
                    VALUES
                        (:user_id, :model_version, :accuracy, now())
                    ON CONFLICT DO NOTHING
                    """
                ),
                {
                    "user_id": user_id,
                    "model_version": version,
                    "accuracy": accuracy,
                },
            )
    except Exception as exc:
        # Log table may not exist yet — don't crash the training task
        log.warning(
            "cognitive_model_log_failed",
            user_id=user_id,
            error=str(exc),
        )
    finally:
        engine.dispose()


@celery_app.task(
    name="hub.retrain_cognitive_model",
    queue="light",
    bind=True,
    max_retries=1,
    default_retry_delay=60,
)
def retrain_cognitive_model_task(self: Any, *, user_id: str) -> None:
    """Weekly beat task: re-train the cognitive load model for *user_id*.

    Steps:
    1. Load productivity_events from DB (last 90 days).
    2. Build feature matrix: [hour_of_day, day_of_week, is_weekend, days_until_weekend].
       Label = 1 if completed and not deferred, else 0.
    3. Skip if fewer than MIN_EVENTS_FOR_TRAINING events are available.
    4. Train RandomForestClassifier(n_estimators=100).
    5. Pickle and store in Redis with 7-day TTL.
    6. Log model version to hub_cognitive_model_log.
    """
    log.info("retrain_cognitive_model_start", user_id=user_id)

    try:
        from sklearn.ensemble import RandomForestClassifier  # type: ignore[import]

        events = _fetch_productivity_events(days=90)

        if len(events) < _MIN_EVENTS_FOR_TRAINING:
            log.warning(
                "retrain_cognitive_model_insufficient_data",
                user_id=user_id,
                event_count=len(events),
                minimum=_MIN_EVENTS_FOR_TRAINING,
            )
            return

        X, y = _build_feature_matrix(events)

        clf = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
        clf.fit(X, y)

        model_bytes = pickle.dumps(clf)

        redis = _get_redis_sync()
        cache_key = _MODEL_CACHE_KEY.format(user_id=user_id)
        redis.setex(cache_key, _MODEL_TTL, model_bytes)

        log.info(
            "retrain_cognitive_model_done",
            user_id=user_id,
            event_count=len(events),
            model_bytes=len(model_bytes),
        )
        _log_model_version(user_id=user_id, version="ml_v1", accuracy=None)

    except Exception as exc:
        log.error("retrain_cognitive_model_error", user_id=user_id, error=str(exc))
        raise self.retry(exc=exc)


@celery_app.task(
    name="hub.check_model_drift",
    queue="light",
    bind=True,
    max_retries=1,
    default_retry_delay=30,
)
def check_model_drift_task(self: Any, *, user_id: str) -> None:
    """Check model drift: if accuracy on the last 7 days drops below threshold,
    revert to rule-based model by deleting the Redis key.
    """
    log.info("check_model_drift_start", user_id=user_id)

    try:
        from sklearn.ensemble import RandomForestClassifier  # type: ignore[import]

        redis = _get_redis_sync()
        cache_key = _MODEL_CACHE_KEY.format(user_id=user_id)
        raw = redis.get(cache_key)

        if raw is None:
            log.info(
                "check_model_drift_no_model",
                user_id=user_id,
            )
            return

        clf: RandomForestClassifier = pickle.loads(raw)  # noqa: S301

        events_7d = _fetch_productivity_events(days=7)
        if len(events_7d) < 5:
            log.info(
                "check_model_drift_insufficient_data",
                user_id=user_id,
                event_count=len(events_7d),
            )
            return

        X, y = _build_feature_matrix(events_7d)
        predictions = clf.predict(X)
        correct = sum(p == label for p, label in zip(predictions, y))
        accuracy = correct / len(y)

        log.info(
            "check_model_drift_accuracy",
            user_id=user_id,
            accuracy=accuracy,
            threshold=_DRIFT_ACCURACY_THRESHOLD,
        )

        if accuracy < _DRIFT_ACCURACY_THRESHOLD:
            log.warning(
                "check_model_drift_reverting",
                user_id=user_id,
                accuracy=accuracy,
            )
            # Remove the cached model so the factory falls back to rule_based
            redis.delete(cache_key)
            # Signal to the env-level factory (best effort — only works if single process)
            os.environ[_COGNITIVE_MODEL_VERSION_ENV] = "rule_based"
            _log_model_version(user_id=user_id, version="rule_based_fallback", accuracy=accuracy)
        else:
            _log_model_version(user_id=user_id, version="ml_v1", accuracy=accuracy)

    except Exception as exc:
        log.error("check_model_drift_error", user_id=user_id, error=str(exc))
        raise self.retry(exc=exc)
