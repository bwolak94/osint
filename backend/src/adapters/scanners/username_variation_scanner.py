"""Username Variation Scanner — AI-enhanced username hunting with variation generation.

Scans usernames at three configurable depths (basic / intermediate / advanced),
automatically generating username variants and checking each against the full
platform registry with an enhanced multi-factor confidence scoring engine.

Scan levels
-----------
- basic:        exact username only (40+ platforms)
- intermediate: adds underscore / dot / numeric variations (~15 variants × platforms)
- advanced:     adds real/official/iam/the prefix + suffix combos (~30 variants × platforms)

Enhanced scoring factors vs standard username_intel_scanner
-----------------------------------------------------------
- HTTP status:       200=+5, 404=-10, 5xx=-3 (vs +2/-3 in base scanner)
- Response timing:   fast non-200 response < 500ms = -2 (bots return instant 404)
- Negative keywords: global not-found keyword list = -2 per match (capped)
- Positive keywords: follow/subscribe/profile etc = +1.5 per match (capped at +3)
- DOM structure:     error CSS classes = -3 each, profile CSS classes = +4 each
- Meta tag analysis: username in <title>/og:title = +5, error keyword in meta = -3
- URL integrity:     redirected away from username = -1

All results for each variation are aggregated and deduplicated — only the
highest-confidence hit per platform is surfaced in found_profiles.
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Literal

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.adapters.scanners.platform_registry import PlatformEntry, all_platforms
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger(__name__)

# ── Runtime constants ──────────────────────────────────────────────────────────

_CONCURRENCY = 30
_REQUEST_TIMEOUT = 10
_BODY_READ_LIMIT = 32_768  # 32 KB — enough for DOM / meta analysis
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)

# Score thresholds for status classification
_FOUND_THRESHOLD: float = 8.0
_NOT_FOUND_THRESHOLD: float = -8.0

# (min_abs_score, confidence) — first match wins
_CONFIDENCE_TIERS: tuple[tuple[float, float], ...] = (
    (10.0, 0.95),
    (6.0, 0.85),
    (2.0, 0.70),
    (0.0, 0.55),
)

# ── Variation generation constants ─────────────────────────────────────────────

_INTERMEDIATE_NUMERIC_SUFFIXES: tuple[str, ...] = (
    "1", "2", "21", "123", "007", "098", "x",
)
_ADVANCED_PREFIXES: tuple[str, ...] = (
    "real", "official", "the", "iam", "thisis", "yo", "itz", "mr", "im",
)
_ADVANCED_SUFFIXES: tuple[str, ...] = (
    "official", "verified", "original", "tv", "live", "online", "zone", "plus", "hq",
)

# ── Regex patterns for DOM / meta analysis ────────────────────────────────────

_DOM_ERROR_RE = re.compile(
    r'(?:class|id)=["\'][^"\']*'
    r'(?:error|not[-_]found|404|page[-_]not[-_]found|no[-_]user|unavailable)'
    r'[^"\']*["\']',
    re.IGNORECASE,
)
_DOM_PROFILE_RE = re.compile(
    r'(?:class|id)=["\'][^"\']*'
    r'(?:profile|user[-_]info|account|bio|avatar|handle|username)'
    r'[^"\']*["\']',
    re.IGNORECASE,
)
_META_TITLE_RE = re.compile(r'<title[^>]*>([^<]{1,200})</title>', re.IGNORECASE)
_META_OG_TITLE_RE = re.compile(
    r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']{1,200})["\']',
    re.IGNORECASE,
)
_META_DESC_RE = re.compile(
    r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']{1,200})["\']',
    re.IGNORECASE,
)

# ── Keyword lists ─────────────────────────────────────────────────────────────

_NEGATIVE_KEYWORDS: tuple[str, ...] = (
    "not found",
    "doesn't exist",
    "does not exist",
    "no such user",
    "user not found",
    "page not found",
    "account not found",
    "this account doesn't exist",
    "sorry, we couldn't find",
    "couldn't find this",
    "no longer available",
    "this page isn't available",
    "been removed",
)
_POSITIVE_KEYWORDS: tuple[str, ...] = (
    "follow",
    "subscribe",
    "followers",
    "following",
    "posts",
    "verified",
    "profile",
    "biography",
    "bio",
    "message",
    "about me",
    "joined",
    "member since",
    "activity",
)

# ── Type alias ────────────────────────────────────────────────────────────────

ScanLevel = Literal["basic", "intermediate", "advanced"]


# ── Domain objects ────────────────────────────────────────────────────────────


class ProfileStatus(str, Enum):
    FOUND = "found"
    MAYBE = "maybe"
    NOT_FOUND = "not_found"
    ERROR = "error"


@dataclass
class VariationResult:
    variation: str
    platform: str
    category: str
    url: str
    status: ProfileStatus
    confidence: float
    http_status: int
    response_ms: int
    score: float
    matched_indicators: list[str]


# ── Username variation generator ──────────────────────────────────────────────


class UsernameVariationGenerator:
    """Generates username variants for a given scan level.

    basic:        [username]
    intermediate: + underscore/dot/numeric transforms
    advanced:     + all intermediate + prefix/suffix combos
    """

    @classmethod
    def generate(cls, username: str, level: ScanLevel) -> list[str]:
        base = username.lower().strip()

        if level == "basic":
            return [base]

        variants: list[str] = [base]

        # Intermediate transforms
        variants += [
            f"{base}_",
            f"_{base}",
            f"{base}.",
            f".{base}",
            f"__{base}",
            f"__{base}__",
        ]
        for suffix in _INTERMEDIATE_NUMERIC_SUFFIXES:
            variants.append(f"{base}{suffix}")

        if " " in base:
            variants.append(base.replace(" ", "_"))
            variants.append(base.replace(" ", "."))

        if level == "intermediate":
            return list(dict.fromkeys(variants))

        # Advanced: prefix + suffix combinations
        for prefix in _ADVANCED_PREFIXES:
            variants.append(f"{prefix}{base}")
            variants.append(f"{prefix}_{base}")
        for sfx in _ADVANCED_SUFFIXES:
            variants.append(f"{base}{sfx}")
            variants.append(f"{base}_{sfx}")

        return list(dict.fromkeys(variants))


# ── Enhanced scoring engine ───────────────────────────────────────────────────


def _score_response(
    *,
    username: str,
    url: str,
    final_url: str,
    http_status: int,
    body: str,
    response_ms: int,
    entry: PlatformEntry,
) -> tuple[ProfileStatus, float, float, list[str]]:
    """Score a single HTTP response and return (status, confidence, raw_score, indicators)."""
    score: float = 0.0
    matched: list[str] = []
    body_lower = body.lower()

    # ── HTTP status ────────────────────────────────────────────────────────────
    if http_status == 200:
        score += 5.0
        matched.append("http_200")
    elif http_status in (301, 302, 303, 307, 308):
        score += 1.0
    elif http_status == 404:
        score -= 10.0
        matched.append("http_404")
    elif http_status >= 500:
        score -= 3.0
        matched.append(f"http_{http_status}")
    # 403 / 429 are ambiguous — neither confirm nor deny

    # ── Response timing heuristic ─────────────────────────────────────────────
    # A non-200 that arrives in < 500 ms is likely an instant "does not exist"
    if http_status != 200 and response_ms < 500:
        score -= 2.0
        matched.append("fast_not_found_response")

    # ── Platform-specific not-found indicators ────────────────────────────────
    for indicator in entry.not_found_indicators:
        if indicator and indicator.lower() in body_lower:
            score -= 2.0
            matched.append(f"platform_not_found:{indicator[:30]}")

    # ── Global negative keyword scan (count once) ─────────────────────────────
    for keyword in _NEGATIVE_KEYWORDS:
        if keyword in body_lower:
            score -= 2.0
            matched.append(f"neg_keyword:{keyword[:30]}")
            break

    # ── Platform-specific found indicators ───────────────────────────────────
    for indicator in entry.found_indicators:
        if indicator and indicator.lower() in body_lower:
            score += 1.0
            matched.append(f"platform_found:{indicator[:30]}")

    # ── Global positive keyword scan (capped at +3) ───────────────────────────
    pos_hits = sum(1 for kw in _POSITIVE_KEYWORDS if kw in body_lower)
    if pos_hits:
        bonus = round(min(3.0, pos_hits * 1.5), 1)
        score += bonus
        matched.append(f"pos_keywords:{pos_hits}")

    # ── DOM structure analysis ────────────────────────────────────────────────
    error_nodes = len(_DOM_ERROR_RE.findall(body))
    if error_nodes:
        penalty = min(6.0, error_nodes * 3.0)
        score -= penalty
        matched.append(f"dom_error_nodes:{error_nodes}")

    profile_nodes = len(_DOM_PROFILE_RE.findall(body))
    if profile_nodes:
        bonus = min(8.0, profile_nodes * 4.0)
        score += bonus
        matched.append(f"dom_profile_nodes:{profile_nodes}")

    # ── Meta tag analysis ─────────────────────────────────────────────────────
    meta_parts: list[str] = []
    for pattern in (_META_TITLE_RE, _META_OG_TITLE_RE, _META_DESC_RE):
        m = pattern.search(body)
        if m:
            meta_parts.append(m.group(1).lower())
    meta_text = " ".join(meta_parts)

    if meta_text:
        if username.lower() in meta_text:
            score += 5.0
            matched.append("username_in_meta")
        for kw in _NEGATIVE_KEYWORDS[:6]:
            if kw in meta_text:
                score -= 3.0
                matched.append(f"meta_neg:{kw[:20]}")
                break
        for kw in _POSITIVE_KEYWORDS[:6]:
            if kw in meta_text:
                score += 2.0
                matched.append(f"meta_pos:{kw[:20]}")
                break

    # ── URL integrity — redirect-away penalty ─────────────────────────────────
    if username.lower() in final_url.lower():
        score += 1.0
    elif http_status == 200 and username.lower() not in final_url.lower():
        score -= 1.0
        matched.append("redirected_away")

    # ── Apply platform reliability weight ─────────────────────────────────────
    weighted = round(score * entry.confidence_weight, 2)

    # ── Classify status ───────────────────────────────────────────────────────
    if weighted >= _FOUND_THRESHOLD:
        status = ProfileStatus.FOUND
    elif weighted <= _NOT_FOUND_THRESHOLD:
        status = ProfileStatus.NOT_FOUND
    else:
        status = ProfileStatus.MAYBE

    abs_w = abs(weighted)
    confidence = 0.55
    for threshold, conf in _CONFIDENCE_TIERS:
        if abs_w > threshold:
            confidence = conf
            break

    return status, round(confidence, 3), weighted, matched


# ── Main scanner class ────────────────────────────────────────────────────────


class UsernameVariationScanner(BaseOsintScanner):
    """AI-enhanced multi-platform username hunter with variation generation.

    Three instances are registered — one per scan level — so the orchestrator
    can select the appropriate depth:

        username_variation_basic        — exact username, 90+ platforms
        username_variation_intermediate — ~15 variants × platforms
        username_variation_advanced     — ~50 variants × platforms

    The enhanced scoring engine layers DOM structure analysis, meta tag
    heuristics, and response timing penalties over the HTTP / content checks
    already present in UsernameIntelScanner, reducing false positives on
    platforms that return HTTP 200 for every URL.
    """

    supported_input_types = frozenset({ScanInputType.USERNAME, ScanInputType.EMAIL})
    cache_ttl = 7200
    scan_timeout = 240
    source_confidence = 0.80

    def __init__(self, scan_level: ScanLevel = "intermediate", **kwargs: Any) -> None:
        self._scan_level: ScanLevel = scan_level
        self.scanner_name = f"username_variation_{scan_level}"
        super().__init__(**kwargs)

    # ── Entry point ───────────────────────────────────────────────────────────

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        username = self._normalize_username(input_value, input_type)
        if not username:
            return self._empty_result(input_value, "Could not extract a valid username")

        variations = UsernameVariationGenerator.generate(username, self._scan_level)
        platforms = all_platforms()

        log.info(
            "aliens_eye_scan_start",
            username=username,
            scan_level=self._scan_level,
            variations=len(variations),
            platforms=len(platforms),
        )

        t0 = time.monotonic()
        all_results = await self._scan_all(variations, platforms)
        elapsed_ms = int((time.monotonic() - t0) * 1000)

        found = [r for r in all_results if r.status == ProfileStatus.FOUND]
        maybe = [r for r in all_results if r.status == ProfileStatus.MAYBE]

        best_found = self._best_per_platform(found)
        best_maybe = self._best_per_platform(maybe)
        # Remove platforms already confirmed found from the maybe list
        found_platforms = {r.platform for r in best_found}
        best_maybe = [r for r in best_maybe if r.platform not in found_platforms]

        log.info(
            "aliens_eye_scan_done",
            username=username,
            scan_level=self._scan_level,
            found=len(best_found),
            maybe=len(best_maybe),
            elapsed_ms=elapsed_ms,
        )

        return {
            "username": username,
            "scan_level": self._scan_level,
            "original_input": input_value,
            "input_type": input_type.value,
            "variations_checked": variations,
            "platforms_checked": len(platforms),
            "total_checks_performed": len(variations) * len(platforms),
            "found_count": len(best_found),
            "maybe_count": len(best_maybe),
            "profiles": [asdict(r) for r in all_results],
            "found_profiles": [asdict(r) for r in best_found],
            "maybe_profiles": [asdict(r) for r in best_maybe],
            "social_profile_urls": [r.url for r in best_found],
            "extracted_identifiers": self._build_identifiers(username, best_found, best_maybe),
            "elapsed_ms": elapsed_ms,
        }

    # ── Concurrent platform scanning ──────────────────────────────────────────

    async def _scan_all(
        self,
        variations: list[str],
        platforms: dict[str, PlatformEntry],
    ) -> list[VariationResult]:
        semaphore = asyncio.Semaphore(_CONCURRENCY)
        tasks = [
            self._check_one(variation, name, entry, semaphore)
            for variation in variations
            for name, entry in platforms.items()
        ]
        raw = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in raw if isinstance(r, VariationResult)]

    async def _check_one(
        self,
        variation: str,
        platform_name: str,
        entry: PlatformEntry,
        semaphore: asyncio.Semaphore,
    ) -> VariationResult:
        url = entry.url_template.format(username=variation)
        t0 = time.monotonic()

        async with semaphore:
            try:
                async with httpx.AsyncClient(
                    timeout=_REQUEST_TIMEOUT,
                    follow_redirects=True,
                    headers={"User-Agent": _USER_AGENT},
                ) as client:
                    resp = await client.get(url)
                    body = (await resp.aread())[:_BODY_READ_LIMIT].decode(errors="replace")
                    response_ms = int((time.monotonic() - t0) * 1000)

                status, confidence, score, matched = _score_response(
                    username=variation,
                    url=url,
                    final_url=str(resp.url),
                    http_status=resp.status_code,
                    body=body,
                    response_ms=response_ms,
                    entry=entry,
                )
                return VariationResult(
                    variation=variation,
                    platform=platform_name,
                    category=entry.category,
                    url=url,
                    status=status,
                    confidence=confidence,
                    http_status=resp.status_code,
                    response_ms=response_ms,
                    score=score,
                    matched_indicators=matched,
                )

            except Exception as exc:
                return VariationResult(
                    variation=variation,
                    platform=platform_name,
                    category=entry.category,
                    url=url,
                    status=ProfileStatus.ERROR,
                    confidence=0.0,
                    http_status=0,
                    response_ms=int((time.monotonic() - t0) * 1000),
                    score=0.0,
                    matched_indicators=[f"error:{type(exc).__name__}"],
                )

    # ── Result aggregation ────────────────────────────────────────────────────

    @staticmethod
    def _best_per_platform(results: list[VariationResult]) -> list[VariationResult]:
        """Return the highest-confidence result per platform, sorted descending."""
        best: dict[str, VariationResult] = {}
        for r in results:
            if r.platform not in best or r.confidence > best[r.platform].confidence:
                best[r.platform] = r
        return sorted(best.values(), key=lambda x: x.confidence, reverse=True)

    @staticmethod
    def _build_identifiers(
        username: str,
        found: list[VariationResult],
        maybe: list[VariationResult],
    ) -> list[str]:
        ids: list[str] = [f"username:{username}"]
        for r in found:
            ids.append(f"social_profile:{r.platform}:{r.url}")
            ids.append(f"url:{r.url}")
        for r in maybe:
            ids.append(f"social_profile_maybe:{r.platform}:{r.url}")
        return ids

    # ── BaseOsintScanner overrides ────────────────────────────────────────────

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])

    def _compute_confidence(self, raw_data: dict[str, Any], extracted: list[str]) -> float:
        if raw_data.get("_stub") or raw_data.get("_not_found"):
            return 0.0
        found = raw_data.get("found_count", 0)
        maybe = raw_data.get("maybe_count", 0)
        total = max(raw_data.get("platforms_checked", 1), 1)
        ratio = (found + maybe * 0.5) / total
        return round(min(0.95, self.source_confidence * (0.2 + 0.8 * min(1.0, ratio * 5))), 4)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _normalize_username(value: str, input_type: ScanInputType) -> str:
        v = value.strip()
        if input_type == ScanInputType.EMAIL and "@" in v:
            return v.split("@")[0].lower()
        return v.lower()

    @staticmethod
    def _empty_result(input_value: str, reason: str) -> dict[str, Any]:
        return {
            "username": "",
            "original_input": input_value,
            "error": reason,
            "scan_level": "",
            "variations_checked": [],
            "platforms_checked": 0,
            "total_checks_performed": 0,
            "found_count": 0,
            "maybe_count": 0,
            "profiles": [],
            "found_profiles": [],
            "maybe_profiles": [],
            "social_profile_urls": [],
            "extracted_identifiers": [],
            "elapsed_ms": 0,
        }
