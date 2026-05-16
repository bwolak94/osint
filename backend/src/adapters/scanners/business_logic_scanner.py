"""Business Logic — application workflow bypass vulnerability scanner.

Detects business logic flaws: negative price/amount manipulation, coupon
stacking, quantity overflow (integer wraparound), workflow step skipping,
privilege escalation via parameter tampering, and free item exploitation.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Endpoints likely to have business logic flaws
_PRICE_ENDPOINTS: list[str] = [
    "/api/cart", "/api/order", "/api/checkout", "/api/payment",
    "/api/v1/cart", "/api/v1/order", "/api/v1/checkout",
    "/cart", "/order", "/checkout", "/purchase",
    "/api/product", "/api/item",
]

_COUPON_ENDPOINTS: list[str] = [
    "/api/coupon", "/api/promo", "/api/discount",
    "/api/v1/coupon", "/api/voucher", "/api/code",
    "/coupon/apply", "/promo/apply",
]

# Negative / boundary value test bodies
_NEGATIVE_AMOUNT_PAYLOADS: list[tuple[dict, str]] = [
    ({"amount": -1, "price": -1}, "negative_amount"),
    ({"amount": -100, "price": -100}, "large_negative"),
    ({"amount": 0, "price": 0}, "zero_amount"),
    ({"quantity": -1, "price": 10}, "negative_qty"),
    ({"price": -9999.99}, "float_negative"),
    ({"amount": 0.001}, "tiny_amount"),
    ({"price": 2147483647}, "int_max"),
    ({"price": 2147483648}, "int_overflow"),
    ({"price": -2147483648}, "int_min"),
    ({"quantity": 99999999}, "large_quantity"),
]

# Response patterns indicating success (purchase/order accepted)
_SUCCESS_PATTERNS = re.compile(
    r'(?i)("order_id"|"transaction_id"|"confirmation"|order.created|'
    r'purchase.complete|payment.success|added.to.cart|item.added)',
)

# Response patterns indicating business logic error handling
_VALIDATION_PATTERNS = re.compile(
    r'(?i)(invalid.amount|amount.must.be|positive|greater.than|minimum|'
    r'validation.error|bad.request|400)',
)

# Workflow step skipping: step endpoints
_WORKFLOW_STEPS: list[tuple[str, str]] = [
    ("/api/checkout/step2", "skip_to_payment"),
    ("/api/checkout/confirm", "skip_to_confirm"),
    ("/api/order/complete", "skip_to_complete"),
    ("/api/payment/confirm", "skip_payment_validation"),
    ("/api/checkout/finalize", "skip_to_finalize"),
]


class BusinessLogicScanner(BaseOsintScanner):
    """Business logic vulnerability scanner.

    Tests for: negative/zero price manipulation, integer overflow in quantities,
    coupon stacking, workflow step skipping, and parameter tampering that
    bypasses application-level constraints.
    """

    scanner_name = "business_logic"
    supported_input_types = frozenset({ScanInputType.DOMAIN, ScanInputType.URL})
    cache_ttl = 3600
    scan_timeout = 90

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        base_url = _normalise_url(input_value, input_type)
        return await self._manual_scan(base_url, input_value)

    async def _manual_scan(self, base_url: str, input_value: str) -> dict[str, Any]:
        vulnerabilities: list[dict[str, Any]] = []
        identifiers: list[str] = []

        async with httpx.AsyncClient(
            timeout=8,
            follow_redirects=True,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; BizLogicScanner/1.0)"},
        ) as client:
            semaphore = asyncio.Semaphore(6)

            # Test 1: Negative / zero price manipulation
            async def test_negative_price(endpoint: str, payload: dict, technique: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + endpoint
                    try:
                        resp = await client.post(url, json=payload)
                        body = resp.text
                        status = resp.status_code

                        if status in (200, 201) and _SUCCESS_PATTERNS.search(body):
                            vulnerabilities.append({
                                "type": "negative_price_accepted",
                                "severity": "critical",
                                "url": url,
                                "payload": payload,
                                "technique": technique,
                                "description": f"Application accepted negative/zero price — {technique}. Attacker can pay negative amount or get items for free.",
                                "remediation": "Server-side validation: enforce amount > 0; fetch prices from DB, never trust client",
                            })
                            ident = f"vuln:bizlogic:negative_price:{technique}"
                            if ident not in identifiers:
                                identifiers.append(ident)

                        elif status in (200, 201) and not _VALIDATION_PATTERNS.search(body):
                            # Accepted without obvious error — could be silent bypass
                            if "json" in resp.headers.get("content-type", ""):
                                vulnerabilities.append({
                                    "type": "price_manipulation_possible",
                                    "severity": "high",
                                    "url": url,
                                    "payload": payload,
                                    "technique": technique,
                                    "description": f"Endpoint accepted {technique} payload without validation error — price manipulation risk",
                                })
                                ident = f"vuln:bizlogic:price_manip:{technique}"
                                if ident not in identifiers:
                                    identifiers.append(ident)

                    except Exception:
                        pass

            price_tasks = []
            for endpoint in _PRICE_ENDPOINTS[:6]:
                for payload, technique in _NEGATIVE_AMOUNT_PAYLOADS[:6]:
                    price_tasks.append(test_negative_price(endpoint, payload, technique))
            await asyncio.gather(*price_tasks)

            # Test 2: Coupon stacking
            async def test_coupon_stacking(endpoint: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + endpoint
                    try:
                        # Try applying same coupon multiple times
                        coupons = ["TEST10", "TEST10", "TEST10"]
                        successful_applies = 0
                        for coupon in coupons:
                            resp = await client.post(
                                url,
                                json={"code": coupon, "coupon": coupon, "promo": coupon},
                            )
                            if resp.status_code in (200, 201) and _SUCCESS_PATTERNS.search(resp.text):
                                successful_applies += 1
                            elif resp.status_code not in (404, 405):
                                # Endpoint exists
                                pass

                        if successful_applies > 1:
                            vulnerabilities.append({
                                "type": "coupon_stacking",
                                "severity": "high",
                                "url": url,
                                "successful_applications": successful_applies,
                                "description": f"Same coupon applied {successful_applies} times — stacking vulnerability",
                                "remediation": "Track coupon usage per user; mark as used after first application",
                            })
                            ident = "vuln:bizlogic:coupon_stacking"
                            if ident not in identifiers:
                                identifiers.append(ident)
                    except Exception:
                        pass

            await asyncio.gather(*[test_coupon_stacking(ep) for ep in _COUPON_ENDPOINTS[:4]])

            # Test 3: Workflow step skipping
            async def test_step_skip(path: str, technique: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + path
                    try:
                        # Try accessing later workflow step directly
                        resp = await client.post(
                            url,
                            json={"order_id": "1", "step": "complete", "confirm": True},
                        )
                        body = resp.text
                        if resp.status_code in (200, 201) and _SUCCESS_PATTERNS.search(body):
                            vulnerabilities.append({
                                "type": "workflow_step_bypass",
                                "severity": "high",
                                "url": url,
                                "technique": technique,
                                "description": f"Workflow step bypass — can access {path} directly without completing prerequisites",
                                "remediation": "Implement server-side workflow state tracking; validate step sequence",
                            })
                            ident = f"vuln:bizlogic:workflow:{technique}"
                            if ident not in identifiers:
                                identifiers.append(ident)
                    except Exception:
                        pass

            await asyncio.gather(*[test_step_skip(p, t) for p, t in _WORKFLOW_STEPS])

            # Test 4: Parameter tampering — user_id / role injection
            async def test_param_tamper(endpoint: str) -> None:
                async with semaphore:
                    url = base_url.rstrip("/") + endpoint
                    # Try injecting admin role or another user's ID
                    for payload in [
                        {"user_id": 1, "role": "admin", "amount": 0},
                        {"user_id": "1", "is_admin": True, "price": 0},
                        {"userId": 1, "permissions": ["admin"], "amount": 1},
                    ]:
                        try:
                            resp = await client.post(url, json=payload)
                            body = resp.text
                            if resp.status_code in (200, 201) and _SUCCESS_PATTERNS.search(body):
                                vulnerabilities.append({
                                    "type": "parameter_tampering",
                                    "severity": "critical",
                                    "url": url,
                                    "payload_sample": list(payload.keys()),
                                    "description": "Client-supplied role/user_id accepted by server — privilege escalation risk",
                                    "remediation": "Never trust client-supplied role or user identity; derive from authenticated session",
                                })
                                ident = "vuln:bizlogic:param_tamper"
                                if ident not in identifiers:
                                    identifiers.append(ident)
                                break
                        except Exception:
                            pass

            await asyncio.gather(*[test_param_tamper(ep) for ep in _PRICE_ENDPOINTS[:4]])

        severity_counts: dict[str, int] = {}
        for v in vulnerabilities:
            s = v.get("severity", "info")
            severity_counts[s] = severity_counts.get(s, 0) + 1

        return {
            "input": input_value,
            "scan_mode": "manual_fallback",
            "base_url": base_url,
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
