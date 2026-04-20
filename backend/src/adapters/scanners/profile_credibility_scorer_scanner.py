"""Profile Credibility Scorer — behavioral heuristics to identify automated or fake accounts.

Module 34 in the SOCMINT domain. Analyzes publicly available behavioral signals:
account age, post frequency, follower/following ratio, profile completeness, and
posting patterns to compute a credibility score (0-100, higher = more credible).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()


def _score_account_age_days(age_days: float) -> int:
    """Score based on account age: older accounts are more credible (max 25 pts)."""
    if age_days >= 365 * 3:
        return 25
    if age_days >= 365:
        return 20
    if age_days >= 180:
        return 15
    if age_days >= 30:
        return 8
    return 2


def _score_activity_ratio(posts: int, age_days: float) -> int:
    """Score posting frequency: abnormally high = suspicious (max 20 pts)."""
    if age_days <= 0:
        return 0
    posts_per_day = posts / age_days
    if posts_per_day > 100:
        return 0  # Bot-like activity
    if posts_per_day > 50:
        return 5
    if posts_per_day > 20:
        return 10
    if posts_per_day > 0.1:
        return 20  # Healthy activity
    return 5  # Very inactive


def _score_karma_ratio(post_karma: int, comment_karma: int) -> int:
    """Score karma distribution: extreme comment/post ratio can indicate spam (max 20 pts)."""
    total = post_karma + comment_karma
    if total <= 0:
        return 5
    comment_ratio = comment_karma / total
    if 0.3 <= comment_ratio <= 0.9:
        return 20  # Balanced
    if 0.1 <= comment_ratio < 0.3:
        return 12
    if comment_ratio >= 0.9:
        return 8  # Mostly comments (possible karma farmer)
    return 5


def _score_profile_completeness(data: dict) -> int:
    """Score based on how complete the profile is (max 25 pts)."""
    score = 0
    if data.get("icon_img") or data.get("snoovatar_img"):
        score += 8   # Has avatar
    if data.get("subreddit", {}).get("public_description"):
        score += 9   # Has bio
    if data.get("verified"):
        score += 8   # Email verified
    return score


def _score_reddit_age(created_utc: float | None) -> tuple[float, int]:
    """Return (age_days, score) for account age."""
    if not created_utc:
        return 0.0, 0
    now = datetime.now(timezone.utc).timestamp()
    age_days = (now - created_utc) / 86400
    return age_days, _score_account_age_days(age_days)


class ProfileCredibilityScorerScanner(BaseOsintScanner):
    """Compute a credibility score for a social media profile using behavioral heuristics.

    Uses Reddit's public API (no key required). Returns a 0-100 score where:
    - 80-100: High credibility (established, active, complete profile)
    - 50-79: Medium credibility (some signals missing)
    - 20-49: Low credibility (several bot-like signals)
    - 0-19: Very low credibility (strong automated account indicators)
    """

    scanner_name = "profile_credibility_scorer"
    supported_input_types = frozenset({ScanInputType.USERNAME})
    cache_ttl = 3600

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        username = input_value.strip().lstrip("@")

        async with httpx.AsyncClient(
            timeout=15,
            headers={"User-Agent": "OSINT-Platform/1.0 CredibilityScorer"},
        ) as client:
            try:
                resp = await client.get(f"https://www.reddit.com/user/{username}/about.json")
                if resp.status_code == 404:
                    return {"found": False, "username": username, "reason": "Account not found"}
                if resp.status_code != 200:
                    return {"found": False, "username": username, "reason": f"HTTP {resp.status_code}"}

                data = resp.json().get("data", {})
            except Exception as exc:
                return {"found": False, "username": username, "error": str(exc)}

        created_utc = data.get("created_utc")
        post_karma = data.get("link_karma", 0) or 0
        comment_karma = data.get("comment_karma", 0) or 0
        total_posts = data.get("total_karma", post_karma + comment_karma)

        age_days, age_score = _score_reddit_age(created_utc)
        activity_score = _score_activity_ratio(total_posts, age_days)
        karma_score = _score_karma_ratio(post_karma, comment_karma)
        completeness_score = _score_profile_completeness(data)

        # Suspicious signals (penalty flags)
        flags: list[str] = []
        if age_days < 7:
            flags.append("Very new account (< 7 days)")
        if age_days > 0 and total_posts / max(age_days, 1) > 50:
            flags.append("Abnormally high posting rate")
        if not data.get("subreddit", {}).get("public_description"):
            flags.append("No profile bio")
        if not (data.get("icon_img") or data.get("snoovatar_img")):
            flags.append("No profile picture")
        if data.get("is_suspended"):
            flags.append("Account suspended")

        total_score = min(100, age_score + activity_score + karma_score + completeness_score)

        # Determine verdict
        if total_score >= 80:
            verdict = "High Credibility"
        elif total_score >= 50:
            verdict = "Medium Credibility"
        elif total_score >= 20:
            verdict = "Low Credibility"
        else:
            verdict = "Very Low Credibility / Possible Bot"

        account_created = (
            datetime.fromtimestamp(created_utc, tz=timezone.utc).isoformat()
            if created_utc else None
        )

        return {
            "found": True,
            "username": username,
            "credibility_score": total_score,
            "verdict": verdict,
            "score_breakdown": {
                "account_age": age_score,
                "activity_ratio": activity_score,
                "karma_distribution": karma_score,
                "profile_completeness": completeness_score,
            },
            "suspicious_flags": flags,
            "account_details": {
                "account_created": account_created,
                "account_age_days": round(age_days, 1),
                "post_karma": post_karma,
                "comment_karma": comment_karma,
                "is_verified": data.get("verified", False),
                "is_suspended": data.get("is_suspended", False),
            },
            "data_source": "reddit_public_api",
        }
