"""Username Intelligence Scanner.

Checks username presence across curated platforms using multi-factor confidence
scoring — HTTP status, content pattern matching, URL structure, and platform
reliability weight. Inspired by username OSINT tooling but built on our own
architecture and scoring model.

Supports:
    - ScanInputType.USERNAME  — direct lookup
    - ScanInputType.EMAIL     — extracts local-part as candidate username
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.adapters.scanners.platform_registry import PlatformEntry, all_platforms
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger(__name__)

# Maximum concurrent platform checks per scan
_CONCURRENCY = 25
# Per-request HTTP timeout (seconds)
_REQUEST_TIMEOUT = 8
# Read at most this many bytes from the response body for content analysis
_BODY_READ_LIMIT = 16_384  # 16 KB
# User-Agent header presented to platforms
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)

# Confidence score thresholds (raw integer points)
_FOUND_THRESHOLD = 3
_MAYBE_THRESHOLD = 1


class ProfileStatus(str, Enum):
    FOUND = "found"
    MAYBE = "maybe"
    NOT_FOUND = "not_found"
    ERROR = "error"


@dataclass
class ProfileResult:
    platform: str
    category: str
    url: str
    status: ProfileStatus
    confidence: float  # 0.0–1.0
    http_status: int
    response_ms: int
    matched_indicators: list[str]


class UsernameIntelScanner(BaseOsintScanner):
    """Multi-platform username presence scanner with confidence scoring.

    Unlike simple HTTP-200 checkers, this scanner applies multi-factor scoring
    to reduce false positives on platforms that return 200 even for ghost URLs:

    Scoring factors (raw integer points per factor):
      +3  HTTP 200 with positive content indicators
      +2  HTTP 200 (baseline)
      +1  Response URL still contains the username (no redirect away)
      -2  Page body contains a known not-found indicator
      -3  HTTP 404 / 410 explicit not-found response
      ×   Multiplied by platform.confidence_weight

    Interpretation:
      score ≥ 3  → Found     (0.65–0.95 confidence)
      score 1–2  → Maybe     (0.40–0.60 confidence)
      score < 1  → Not Found (0.00–0.30 confidence)
    """

    scanner_name = "username_intel"
    supported_input_types = frozenset({ScanInputType.USERNAME, ScanInputType.EMAIL})
    cache_ttl = 7200  # 2 hours — platform availability changes
    scan_timeout = 90
    source_confidence = 0.75

    # ── Entry point ──────────────────────────────────────────────────────────

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        username = self._normalize_username(input_value, input_type)
        if not username:
            return self._empty_result(input_value, "Could not extract a valid username")

        log.info("username_intel_scan_start", username=username, platforms=len(all_platforms()))
        start = time.monotonic()

        results = await self._scan_all_platforms(username)

        elapsed_ms = int((time.monotonic() - start) * 1000)
        found = [r for r in results if r.status == ProfileStatus.FOUND]
        maybe = [r for r in results if r.status == ProfileStatus.MAYBE]

        log.info(
            "username_intel_scan_done",
            username=username,
            found=len(found),
            maybe=len(maybe),
            total=len(results),
            elapsed_ms=elapsed_ms,
        )

        return {
            "username": username,
            "original_input": input_value,
            "input_type": input_type.value,
            "platforms_checked": len(results),
            "found_count": len(found),
            "maybe_count": len(maybe),
            "profiles": [asdict(r) for r in results],
            "found_profiles": [asdict(r) for r in found],
            "social_profile_urls": [r.url for r in found],
            "extracted_identifiers": self._build_identifiers(username, found, maybe),
        }

    # ── Platform scanning ─────────────────────────────────────────────────────

    async def _scan_all_platforms(self, username: str) -> list[ProfileResult]:
        platforms = all_platforms()
        semaphore = asyncio.Semaphore(_CONCURRENCY)
        results: list[ProfileResult] = []

        async def bounded_check(name: str, entry: PlatformEntry) -> None:
            async with semaphore:
                result = await self._check_platform(username, name, entry)
            results.append(result)

        await asyncio.gather(
            *[bounded_check(name, entry) for name, entry in platforms.items()],
            return_exceptions=True,
        )
        return results

    async def _check_platform(
        self, username: str, platform_name: str, entry: PlatformEntry
    ) -> ProfileResult:
        url = entry.url_template.format(username=username)
        t0 = time.monotonic()

        try:
            async with httpx.AsyncClient(
                timeout=_REQUEST_TIMEOUT,
                follow_redirects=True,
                headers={"User-Agent": _USER_AGENT},
            ) as client:
                resp = await client.get(url)
                body = (await resp.aread())[:_BODY_READ_LIMIT].decode(errors="replace")
                response_ms = int((time.monotonic() - t0) * 1000)

            status, confidence, matched = self._score_response(
                username=username,
                url=url,
                final_url=str(resp.url),
                http_status=resp.status_code,
                body=body,
                entry=entry,
            )

            return ProfileResult(
                platform=platform_name,
                category=entry.category,
                url=url,
                status=status,
                confidence=confidence,
                http_status=resp.status_code,
                response_ms=response_ms,
                matched_indicators=matched,
            )

        except Exception as exc:
            return ProfileResult(
                platform=platform_name,
                category=entry.category,
                url=url,
                status=ProfileStatus.ERROR,
                confidence=0.0,
                http_status=0,
                response_ms=int((time.monotonic() - t0) * 1000),
                matched_indicators=[f"error:{type(exc).__name__}"],
            )

    # ── Scoring engine ────────────────────────────────────────────────────────

    def _score_response(
        self,
        *,
        username: str,
        url: str,
        final_url: str,
        http_status: int,
        body: str,
        entry: PlatformEntry,
    ) -> tuple[ProfileStatus, float, list[str]]:
        score = 0
        matched: list[str] = []

        # Factor 1: HTTP status
        if http_status == 200:
            score += 2
        elif http_status in (301, 302, 303, 307, 308):
            score += 1
        elif http_status in (404, 410):
            score -= 3
            matched.append(f"http_{http_status}")
        elif http_status in (403, 429):
            # Ambiguous — neither confirms nor denies
            pass
        else:
            score -= 1

        # Factor 2: Not-found content indicators (body analysis)
        body_lower = body.lower()
        for indicator in entry.not_found_indicators:
            if indicator and indicator.lower() in body_lower:
                score -= 2
                matched.append(f"not_found:{indicator[:40]}")

        # Factor 3: Found content indicators
        for indicator in entry.found_indicators:
            if indicator and indicator.lower() in body_lower:
                score += 1
                matched.append(f"found:{indicator[:40]}")

        # Factor 4: URL integrity — did we get redirected away from the username?
        username_lower = username.lower()
        if username_lower in final_url.lower():
            score += 1
        elif http_status == 200 and username_lower not in final_url.lower():
            # Redirected away — probably not a real profile
            score -= 1

        # Apply platform reliability weight and convert to status + confidence
        weighted = score * entry.confidence_weight

        if weighted >= _FOUND_THRESHOLD:
            status = ProfileStatus.FOUND
            # Map weighted score to [0.65, 0.95]
            confidence = round(min(0.95, 0.65 + (weighted - _FOUND_THRESHOLD) * 0.05), 3)
        elif weighted >= _MAYBE_THRESHOLD:
            status = ProfileStatus.MAYBE
            confidence = round(0.40 + (weighted - _MAYBE_THRESHOLD) * 0.10, 3)
        else:
            status = ProfileStatus.NOT_FOUND
            confidence = round(max(0.0, 0.15 + weighted * 0.05), 3)

        return status, confidence, matched

    # ── Identifier extraction ─────────────────────────────────────────────────

    def _build_identifiers(
        self,
        username: str,
        found: list[ProfileResult],
        maybe: list[ProfileResult],
    ) -> list[str]:
        ids: list[str] = [f"username:{username}"]
        for result in found:
            ids.append(f"social_profile:{result.platform}:{result.url}")
            ids.append(f"url:{result.url}")
        for result in maybe:
            ids.append(f"social_profile_maybe:{result.platform}:{result.url}")
        return ids

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])

    def _compute_confidence(self, raw_data: dict[str, Any], extracted: list[str]) -> float:
        if raw_data.get("_stub") or raw_data.get("_not_found"):
            return 0.0
        found_count: int = raw_data.get("found_count", 0)
        maybe_count: int = raw_data.get("maybe_count", 0)
        total: int = raw_data.get("platforms_checked", 1) or 1

        # Presence ratio weighted by certainty tier
        presence_ratio = (found_count + maybe_count * 0.5) / total
        return round(min(0.95, self.source_confidence * (0.2 + 0.8 * min(1.0, presence_ratio * 5))), 4)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _normalize_username(input_value: str, input_type: ScanInputType) -> str:
        value = input_value.strip()
        if input_type == ScanInputType.EMAIL and "@" in value:
            return value.split("@")[0].lower()
        return value.lower()

    @staticmethod
    def _empty_result(input_value: str, reason: str) -> dict[str, Any]:
        return {
            "username": "",
            "original_input": input_value,
            "error": reason,
            "platforms_checked": 0,
            "found_count": 0,
            "maybe_count": 0,
            "profiles": [],
            "found_profiles": [],
            "social_profile_urls": [],
            "extracted_identifiers": [],
        }
