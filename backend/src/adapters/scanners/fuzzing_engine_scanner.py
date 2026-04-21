"""Fuzzing Engine — tests URL parameters with boundary and anomalous values.

Module 84 in the Infrastructure & Exploitation domain. Probes the target URL's
query parameters with boundary values (empty string, very large integers, null bytes,
format strings) and monitors for HTTP 500 errors, unusual response size deltas, or
unexpected content-type changes. Demonstrates parameter fuzzing as a quality/security
testing technique.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Boundary and anomaly payloads for basic fuzzing
_FUZZ_PAYLOADS: list[dict[str, str]] = [
    {"label": "empty", "value": ""},
    {"label": "null_byte", "value": "\x00"},
    {"label": "large_integer", "value": "999999999999999999"},
    {"label": "negative_integer", "value": "-1"},
    {"label": "float", "value": "1.7976931348623157e+308"},
    {"label": "very_long_string", "value": "A" * 2048},
    {"label": "format_string", "value": "%s%s%s%s%s%s%s%s%n%n%n"},
    {"label": "path_traversal", "value": "../../etc/passwd"},
    {"label": "null_string", "value": "null"},
    {"label": "boolean_true", "value": "true"},
    {"label": "special_chars", "value": "!@#$%^&*(){}[]|;:',.<>?"},
    {"label": "unicode_overflow", "value": "\uffff\ufffe\u0000"},
]

_PROBE_PARAMS = ["id", "page", "q", "search", "category", "type", "action", "file", "path", "name"]


def _normalize_target(input_value: str) -> str:
    value = input_value.strip()
    if not value.startswith(("http://", "https://")):
        value = f"https://{value}"
    return value


def _inject_param(url: str, param: str, value: str) -> str:
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    params[param] = [value]
    new_query = urlencode(params, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


class FuzzingEngineScanner(BaseOsintScanner):
    """Probes URL parameters with boundary and anomalous values to surface errors.

    Tests for HTTP 500 responses, large response size deltas, and content-type
    changes that might indicate unhandled input cases. Only targets the URL/domain
    supplied by the user (Module 84).
    """

    scanner_name = "fuzzing_engine"
    supported_input_types = frozenset({ScanInputType.URL, ScanInputType.DOMAIN})
    cache_ttl = 1800  # 30 minutes

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        target = _normalize_target(input_value)
        parsed = urlparse(target)

        existing_params = list(parse_qs(parsed.query).keys())
        probe_params = list(dict.fromkeys(existing_params + _PROBE_PARAMS))[:6]

        anomalies: list[dict[str, Any]] = []
        all_results: list[dict[str, Any]] = []

        async with httpx.AsyncClient(
            timeout=20,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (OSINT-Security-Research/1.0)"},
        ) as client:
            # Establish baseline
            baseline_size: int = 0
            baseline_status: int = 200
            baseline_content_type: str = "text/html"
            try:
                baseline_resp = await client.get(target)
                baseline_size = len(baseline_resp.content)
                baseline_status = baseline_resp.status_code
                baseline_content_type = baseline_resp.headers.get("content-type", "text/html").split(";")[0].strip()
            except httpx.RequestError:
                pass

            for param in probe_params:
                for fuzz in _FUZZ_PAYLOADS:
                    test_url = _inject_param(target, param, fuzz["value"])
                    record: dict[str, Any] = {
                        "param": param,
                        "fuzz_label": fuzz["label"],
                        "status_code": None,
                        "size": None,
                        "size_delta": None,
                        "content_type": None,
                        "anomaly": False,
                        "anomaly_reason": [],
                    }
                    try:
                        resp = await client.get(test_url)
                        record["status_code"] = resp.status_code
                        record["size"] = len(resp.content)
                        record["size_delta"] = record["size"] - baseline_size
                        record["content_type"] = resp.headers.get("content-type", "").split(";")[0].strip()

                        reasons: list[str] = []
                        if resp.status_code == 500:
                            reasons.append("HTTP 500 Internal Server Error")
                        if abs(record["size_delta"]) > 5000:
                            reasons.append(f"Large size delta: {record['size_delta']} bytes")
                        if record["content_type"] != baseline_content_type:
                            reasons.append(f"Content-type changed to {record['content_type']}")

                        if reasons:
                            record["anomaly"] = True
                            record["anomaly_reason"] = reasons
                            anomalies.append(record)
                    except httpx.TimeoutException:
                        record["anomaly"] = True
                        record["anomaly_reason"] = ["Request timed out — possible DoS/hang condition"]
                        anomalies.append(record)
                    except httpx.RequestError as exc:
                        record["error"] = str(exc)
                    all_results.append(record)

        return {
            "target": target,
            "found": len(anomalies) > 0,
            "baseline_status": baseline_status,
            "baseline_size": baseline_size,
            "total_tests": len(all_results),
            "anomaly_count": len(anomalies),
            "anomalies": anomalies,
            "educational_note": (
                "Fuzzing sends malformed or boundary inputs to parameters to expose unhandled "
                "exceptions, denial-of-service conditions, or logic errors. Anomalous responses "
                "warrant deeper manual investigation."
            ),
        }
