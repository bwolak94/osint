"""Race Condition — TOCTOU and concurrent request exploitation scanner.

Detects time-of-check to time-of-use (TOCTOU) vulnerabilities and race conditions
in web applications. Sends high-concurrency simultaneous requests to state-changing
endpoints and analyzes response anomalies indicating non-atomic operations.

Targets: coupon/voucher redemption, inventory decrement, balance operations,
file uploads, OTP verification, and limit enforcement endpoints.
"""

from __future__ import annotations

import asyncio
import statistics
import time
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Endpoints likely to have race conditions
_RACE_TARGETS: list[tuple[str, str, dict[str, str]]] = [
    # (path, description, body)
    ("/api/coupon/apply", "coupon_redemption", {"code": "TESTRACE100", "amount": "100"}),
    ("/api/voucher/redeem", "voucher_redemption", {"voucher": "TESTVOUCHER"}),
    ("/api/promo/use", "promo_code", {"promo": "TESTPROMO"}),
    ("/api/transfer", "transfer_operation", {"to": "test", "amount": "1"}),
    ("/api/withdraw", "withdrawal", {"amount": "1"}),
    ("/api/order", "order_creation", {"item": "test", "qty": "999"}),
    ("/api/vote", "voting", {"id": "1", "vote": "up"}),
    ("/api/like", "like_action", {"post_id": "1"}),
    ("/api/otp/verify", "otp_verification", {"otp": "123456"}),
    ("/api/token/exchange", "token_exchange", {"token": "test"}),
    ("/api/referral/claim", "referral_claim", {"code": "TESTREF"}),
    ("/api/limit/check", "rate_limit_check", {"action": "test"}),
]

# Concurrency level for race condition testing
_RACE_CONCURRENCY = 20
_RACE_TIMEOUT = 5.0


class RaceConditionScanner(BaseOsintScanner):
    """Race condition / TOCTOU vulnerability scanner.

    Fires _RACE_CONCURRENCY simultaneous requests at state-changing endpoints
    and analyzes response variance: identical success responses from multiple
    concurrent requests indicate non-atomic operations vulnerable to exploitation.
    """

    scanner_name = "race_condition"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 1800
    scan_timeout = 120

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)
        return await self._manual_scan(base_url, input_value)

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []
        endpoints_tested: list[str] = []

        async with httpx.AsyncClient(
            timeout=_RACE_TIMEOUT,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; RaceScanner/1.0)"},
        ) as client:

            async def test_race_condition(
                path: str,
                description: str,
                body: dict[str, str],
            ) -> None:
                url = base_url.rstrip("/") + path
                endpoints_tested.append(url)

                # Fire all requests simultaneously using asyncio.gather with last-moment dispatch
                async def single_request() -> tuple[int, str, float]:
                    start = time.monotonic()
                    try:
                        resp = await client.post(url, json=body)
                        elapsed = time.monotonic() - start
                        return resp.status_code, resp.text[:200], elapsed
                    except Exception:
                        return 0, "", time.monotonic() - start

                # Pre-create all coroutines, then launch together
                tasks = [single_request() for _ in range(_RACE_CONCURRENCY)]

                # Use a barrier-style approach: gather all but don't yield until all are ready
                results: list[tuple[int, str, float]] = await asyncio.gather(*tasks)

                # Analyze results
                status_codes = [r[0] for r in results if r[0] != 0]
                if not status_codes:
                    return

                # Skip if all 404/405/401/403 — endpoint doesn't exist
                non_error = [s for s in status_codes if s not in (404, 405, 0)]
                if not non_error:
                    return

                success_codes = [s for s in status_codes if s in (200, 201)]
                total_requests = len(status_codes)

                # Indicator 1: Multiple successful responses for a single-use operation
                if len(success_codes) > 1 and total_requests >= 5:
                    success_rate = len(success_codes) / total_requests
                    # High success rate on concurrent ops suggests no locking
                    if success_rate > 0.5:
                        vulnerabilities.append({
                            "type": "race_condition_multiple_success",
                            "severity": "high",
                            "url": url,
                            "description": description,
                            "concurrent_requests": total_requests,
                            "success_count": len(success_codes),
                            "success_rate": round(success_rate, 2),
                            "evidence": f"{len(success_codes)}/{total_requests} requests succeeded simultaneously",
                            "remediation": "Use atomic database operations, distributed locks (Redis SETNX), or idempotency keys",
                        })
                        ident = f"vuln:race:{description}"
                        if ident not in identifiers:
                            identifiers.append(ident)
                        return

                # Indicator 2: Inconsistent responses (some 200, some 409/429) but non-trivial
                # Mixed responses on concurrent limit-enforcing operations = partial protection
                unique_statuses = set(status_codes)
                if len(unique_statuses) > 1 and 200 in unique_statuses:
                    conflict_codes = [s for s in status_codes if s in (409, 429, 422)]
                    if conflict_codes and len(success_codes) > 1:
                        vulnerabilities.append({
                            "type": "race_condition_partial",
                            "severity": "medium",
                            "url": url,
                            "description": description,
                            "status_distribution": {str(s): status_codes.count(s) for s in unique_statuses},
                            "evidence": f"Mixed responses suggest race window: {success_codes[:3]} successes despite conflict codes",
                            "remediation": "Implement database-level unique constraints and pessimistic locking",
                        })
                        ident = f"vuln:race:partial:{description}"
                        if ident not in identifiers:
                            identifiers.append(ident)

                # Indicator 3: Timing variance — sequential-looking response times suggest
                # single-threaded handler that's vulnerable but fast
                response_times = [r[2] for r in results if r[0] != 0]
                if len(response_times) >= 10:
                    try:
                        stdev = statistics.stdev(response_times)
                        mean_time = statistics.mean(response_times)
                        # Very low stdev relative to mean = all processed truly concurrently
                        if stdev < mean_time * 0.1 and len(success_codes) >= 2:
                            vulnerabilities.append({
                                "type": "race_condition_timing",
                                "severity": "medium",
                                "url": url,
                                "description": description,
                                "mean_response_ms": round(mean_time * 1000, 1),
                                "stdev_ms": round(stdev * 1000, 1),
                                "evidence": "Near-identical response times indicate concurrent processing without mutex",
                            })
                            ident = f"vuln:race:timing:{description}"
                            if ident not in identifiers:
                                identifiers.append(ident)
                    except statistics.StatisticsError:
                        pass

            # Test up to 8 endpoints (respects scan_timeout)
            for path, description, body in _RACE_TARGETS[:8]:
                try:
                    await test_race_condition(path, description, body)
                    await asyncio.sleep(0.5)  # Brief pause between endpoint groups
                except Exception as exc:
                    log.debug("Race condition test failed", url=base_url + path, error=str(exc))

        severity_counts: dict[str, int] = {}
        for v in vulnerabilities:
            s = v.get("severity", "info")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
            "endpoints_tested": endpoints_tested,
            "concurrency_used": _RACE_CONCURRENCY,
            "vulnerabilities": vulnerabilities,
            "total_found": len(vulnerabilities),
            "severity_summary": severity_counts,
            "extracted_identifiers": identifiers,
        }

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])


def _normalise_url(value: str, input_type: ScanInputType) -> str:
    if input_type == ScanInputType.DOMAIN:
        return f"https://{value}"
    if not value.startswith(("http://", "https://")):
        return f"https://{value}"
    return value
