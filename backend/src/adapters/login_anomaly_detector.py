"""Anomaly detection for login events using heuristic risk scoring."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import structlog

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------


@dataclass
class LoginFeatures:
    """Feature vector extracted from a single login attempt."""

    user_id: str
    ip_address: str
    country_code: str
    city: str
    user_agent: str
    timestamp_hour: int  # 0–23 UTC
    timestamp_weekday: int  # 0 = Monday … 6 = Sunday


@dataclass
class LoginRiskAssessment:
    """Risk verdict produced for a login attempt."""

    risk_score: float  # 0.0 – 1.0 (clamped)
    risk_level: str  # "low" | "medium" | "high" | "critical"
    risk_factors: list[str]
    require_mfa: bool
    block: bool
    explanation: str


# ---------------------------------------------------------------------------
# Redis key helpers
# ---------------------------------------------------------------------------

_REDIS_TTL_SECONDS = 30 * 24 * 3600  # 30 days
_ATTEMPTS_TTL_SECONDS = 5 * 60  # 5-minute velocity window


def _logins_key(user_id: str) -> str:
    return f"logins:{user_id}"


def _attempts_key(user_id: str) -> str:
    return f"login_attempts:{user_id}"


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------


class LoginAnomalyDetector:
    """Score login attempts against a historical baseline using heuristics.

    The detector is stateless except for optional Redis integration.  When a
    Redis client is supplied, velocity-based scoring and login history
    persistence are enabled; without Redis only feature-based heuristics run.
    """

    def __init__(self, redis_client: Any | None = None) -> None:
        self._redis = redis_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def assess(
        self,
        features: LoginFeatures,
        history: list[LoginFeatures],
    ) -> LoginRiskAssessment:
        """Compute a :class:`LoginRiskAssessment` for a login attempt.

        Args:
            features: Feature vector for the current login event.
            history:  The user's last N successful login feature vectors.

        Returns:
            A fully populated :class:`LoginRiskAssessment`.
        """
        risk_factors: list[str] = []
        score: float = 0.0

        # --- IP / location ---
        ip_delta = self._score_ip_change(features, history)
        if ip_delta > 0:
            score += ip_delta
            if features.country_code not in {h.country_code for h in history}:
                risk_factors.append(
                    f"Login from new country: {features.country_code}"
                )
            elif features.city not in {h.city for h in history}:
                risk_factors.append(
                    f"Login from new city in known country: {features.city}"
                )
            else:
                risk_factors.append(f"Login from new IP address: {features.ip_address}")

        # --- Unusual hour ---
        time_delta = self._score_time_anomaly(features, history)
        if time_delta > 0:
            score += time_delta
            risk_factors.append(
                f"Login at unusual hour: {features.timestamp_hour:02d}:00 UTC"
            )

        # --- User-agent change ---
        ua_delta = self._score_ua_change(features, history)
        if ua_delta > 0:
            score += ua_delta
            risk_factors.append("Login from a new browser / device.")

        # --- Velocity (brute force) ---
        velocity_delta = self._score_velocity(features.user_id)
        if velocity_delta > 0:
            score += velocity_delta
            risk_factors.append("Multiple failed login attempts detected (possible brute force).")

        # Clamp to [0.0, 1.0].
        score = min(max(score, 0.0), 1.0)
        level, require_mfa, block = self._compute_risk_level(score)

        explanation = self._build_explanation(score, level, risk_factors)

        log.info(
            "login.risk_assessed",
            user_id=features.user_id,
            score=round(score, 3),
            level=level,
            risk_factors=risk_factors,
            block=block,
        )

        return LoginRiskAssessment(
            risk_score=round(score, 4),
            risk_level=level,
            risk_factors=risk_factors,
            require_mfa=require_mfa,
            block=block,
            explanation=explanation,
        )

    # ------------------------------------------------------------------
    # Scoring sub-components
    # ------------------------------------------------------------------

    def _score_ip_change(
        self, current: LoginFeatures, history: list[LoginFeatures]
    ) -> float:
        """Score IP / location novelty.

        - New country not seen in history      → +0.5
        - Same country but new city            → +0.1
        - Same country + city but new IP       → +0.4
        - IP seen before                       → 0.0
        """
        if not history:
            return 0.0

        known_ips = {h.ip_address for h in history}
        known_countries = {h.country_code for h in history}
        known_cities = {h.city for h in history}

        if current.ip_address in known_ips:
            return 0.0

        if current.country_code not in known_countries:
            return 0.5

        if current.city not in known_cities:
            return 0.1

        # Same country + city, but IP is new.
        return 0.4

    def _score_time_anomaly(
        self, current: LoginFeatures, history: list[LoginFeatures]
    ) -> float:
        """Return +0.2 when the login hour falls outside the user's typical window.

        The "typical window" is ±2 hours around each historically observed hour.
        When there is insufficient history (< 3 events) no penalty is applied.
        """
        if len(history) < 3:
            return 0.0

        typical_hours: set[int] = set()
        for h in history:
            for offset in (-2, -1, 0, 1, 2):
                typical_hours.add((h.timestamp_hour + offset) % 24)

        if current.timestamp_hour not in typical_hours:
            return 0.2

        return 0.0

    def _score_ua_change(
        self, current: LoginFeatures, history: list[LoginFeatures]
    ) -> float:
        """Return +0.15 when the user-agent string has never been seen before."""
        if not history:
            return 0.0

        known_uas = {h.user_agent for h in history}
        if current.user_agent not in known_uas:
            return 0.15

        return 0.0

    def _score_velocity(
        self, user_id: str, window_minutes: int = 5
    ) -> float:
        """Return +0.6 when more than 3 failed attempts are found in Redis.

        Falls back to 0.0 gracefully when Redis is unavailable.
        """
        if self._redis is None:
            return 0.0

        key = _attempts_key(user_id)
        try:
            count_raw = self._redis.get(key)
            count = int(count_raw) if count_raw else 0
        except Exception as exc:  # noqa: BLE001
            log.warning("login.velocity_redis_error", user_id=user_id, error=str(exc))
            return 0.0

        if count > 3:
            log.warning("login.velocity_exceeded", user_id=user_id, count=count)
            return 0.6

        return 0.0

    # ------------------------------------------------------------------
    # Risk level mapping
    # ------------------------------------------------------------------

    def _compute_risk_level(
        self, score: float
    ) -> tuple[str, bool, bool]:
        """Map a raw score to a named level, MFA requirement, and block flag.

        Returns:
            ``(level, require_mfa, block)``

        Thresholds::

            score < 0.3   → low,      no MFA, no block
            0.3 ≤ s < 0.6 → medium,   MFA,    no block
            0.6 ≤ s < 0.8 → high,     MFA,    no block
            score ≥ 0.8   → critical, MFA,    block
        """
        if score >= 0.8:
            return "critical", True, True
        if score >= 0.6:
            return "high", True, False
        if score >= 0.3:
            return "medium", True, False
        return "low", False, False

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    async def record_login(self, features: LoginFeatures, success: bool) -> None:
        """Persist a login event to Redis for future anomaly scoring.

        Successful logins are stored in a sorted set keyed by Unix timestamp.
        Failed attempts increment a short-lived counter used by velocity scoring.
        Both structures carry a 30-day TTL.

        This method is a no-op when no Redis client is configured.
        """
        if self._redis is None:
            return

        now_ts = datetime.now(timezone.utc).timestamp()

        if success:
            key = _logins_key(features.user_id)
            payload = (
                f"{features.ip_address}|{features.country_code}|{features.city}"
                f"|{features.user_agent}|{features.timestamp_hour}"
                f"|{features.timestamp_weekday}"
            )
            try:
                self._redis.zadd(key, {payload: now_ts})
                self._redis.expire(key, _REDIS_TTL_SECONDS)
                log.debug("login.recorded", user_id=features.user_id, success=True)
            except Exception as exc:  # noqa: BLE001
                log.error("login.record_failed", user_id=features.user_id, error=str(exc))
        else:
            attempts_key = _attempts_key(features.user_id)
            try:
                self._redis.incr(attempts_key)
                self._redis.expire(attempts_key, _ATTEMPTS_TTL_SECONDS)
                log.debug("login.recorded", user_id=features.user_id, success=False)
            except Exception as exc:  # noqa: BLE001
                log.error(
                    "login.record_attempt_failed",
                    user_id=features.user_id,
                    error=str(exc),
                )

    async def get_history(self, user_id: str, limit: int = 20) -> list[dict]:
        """Retrieve recent login history from Redis sorted set.

        Returns a list of login event dicts ordered newest-first.  Returns an
        empty list when Redis is unavailable or the user has no stored history.
        """
        if self._redis is None:
            return []

        key = _logins_key(user_id)
        try:
            # ZRANGE with REV and LIMIT fetches newest entries first.
            members = self._redis.zrange(key, 0, limit - 1, rev=True, withscores=True)
        except Exception as exc:  # noqa: BLE001
            log.error("login.history_fetch_failed", user_id=user_id, error=str(exc))
            return []

        results: list[dict] = []
        for payload, timestamp in members:
            decoded = payload.decode() if isinstance(payload, bytes) else payload
            parts = decoded.split("|")
            if len(parts) == 6:  # noqa: PLR2004
                results.append(
                    {
                        "ip_address": parts[0],
                        "country_code": parts[1],
                        "city": parts[2],
                        "user_agent": parts[3],
                        "timestamp_hour": int(parts[4]),
                        "timestamp_weekday": int(parts[5]),
                        "recorded_at": datetime.fromtimestamp(
                            float(timestamp), tz=timezone.utc
                        ).isoformat(),
                    }
                )

        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_explanation(
        score: float, level: str, risk_factors: list[str]
    ) -> str:
        if not risk_factors:
            return f"Login appears normal (risk score: {score:.2f})."

        factors_text = "; ".join(risk_factors)
        return (
            f"Risk level '{level}' (score: {score:.2f}). "
            f"Contributing factors: {factors_text}."
        )
