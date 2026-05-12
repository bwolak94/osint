"""XSS Payload Tester — tests target URLs for reflected cross-site scripting vulnerabilities.

Module 81 in the Infrastructure & Exploitation domain. Injects benign detection payloads
into URL query parameters of the user-supplied target and checks whether the payload
appears unescaped in the response body. Educational tool demonstrating how reflected
XSS is discovered during security assessments.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# Benign detection payloads — no actual JavaScript execution intent;
# used solely to detect whether the string appears reflected in HTML output.
_XSS_PAYLOADS: list[str] = [
    "<script>alert(1)</script>",
    '"><script>alert(1)</script>',
    "'><script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    "<svg onload=alert(1)>",
    "javascript:alert(1)",
    '"><img src=x onerror=alert(1)>',
    "<body onload=alert(1)>",
]

_DB_ERROR_PATTERNS = re.compile(
    r"(sql syntax|mysql_fetch|pg_query|sqlite3|ora-\d{5}|syntax error near)",
    re.IGNORECASE,
)


def _normalize_target(input_value: str) -> str:
    """Ensure the input value is a full URL with a scheme."""
    value = input_value.strip()
    if not value.startswith(("http://", "https://")):
        value = f"https://{value}"
    return value


def _inject_payload_into_url(url: str, param: str, payload: str) -> str:
    """Replace or add a query parameter with the payload."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    params[param] = [payload]
    new_query = urlencode(params, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


class XSSPayloadTesterScanner(BaseOsintScanner):
    """Tests target URLs for reflected XSS by injecting benign detection payloads.

    Only targets the URL/domain supplied by the user. Tests each existing query
    parameter and a synthetic 'q' probe parameter. Reports reflected payloads
    and provides remediation guidance (Module 81).
    """

    scanner_name = "xss_payload_tester"
    supported_input_types = frozenset({ScanInputType.URL, ScanInputType.DOMAIN})
    cache_ttl = 3600  # 1 hour — page behaviour changes frequently

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        target = _normalize_target(input_value)
        parsed = urlparse(target)

        # Build the list of parameters to probe
        existing_params = list(parse_qs(parsed.query).keys())
        probe_params = list(dict.fromkeys(existing_params + ["q", "search", "id", "page", "query"]))

        tested: list[dict[str, Any]] = []
        reflected: list[dict[str, Any]] = []

        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (OSINT-Security-Research/1.0)"},
        ) as client:
            for param in probe_params[:5]:  # Cap to avoid excessive requests
                for payload in _XSS_PAYLOADS[:4]:  # Use first 4 payloads per param
                    test_url = _inject_payload_into_url(target, param, payload)
                    record: dict[str, Any] = {
                        "url": test_url,
                        "param": param,
                        "payload": payload,
                        "reflected": False,
                        "status_code": None,
                        "evidence": "",
                    }
                    try:
                        resp = await client.get(test_url)
                        record["status_code"] = resp.status_code
                        body = resp.text
                        if payload in body:
                            record["reflected"] = True
                            # Capture a small context snippet around the reflection
                            idx = body.find(payload)
                            snippet_start = max(0, idx - 40)
                            snippet_end = min(len(body), idx + len(payload) + 40)
                            record["evidence"] = body[snippet_start:snippet_end]
                            reflected.append(record)
                    except httpx.RequestError as exc:
                        record["error"] = str(exc)
                    tested.append(record)

        vulnerability_found = len(reflected) > 0

        recommendations = [
            "Encode all user-supplied data before rendering it in HTML (use htmlspecialchars or equivalent).",
            "Implement a strict Content-Security-Policy (CSP) header.",
            "Use framework-level auto-escaping (e.g., Jinja2 autoescape, React JSX).",
            "Validate and whitelist expected input formats on the server side.",
        ]

        return {
            "target": target,
            "found": vulnerability_found,
            "tested_count": len(tested),
            "reflected_count": len(reflected),
            "tested_payloads": tested,
            "reflected_payloads": reflected,
            "vulnerability_found": vulnerability_found,
            "severity": "High" if vulnerability_found else "None",
            "recommendations": recommendations,
            "educational_note": (
                "Reflected XSS occurs when user input is immediately echoed back in a "
                "response without sanitisation. This scanner tests benign detection strings only."
            ),
        }
