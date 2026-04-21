"""JWT Security Auditor — discovers and audits JWT tokens in HTTP responses.

Module 101 in the Infrastructure & Exploitation domain. Fetches the target URL
and scans response headers, cookies, and body for JWT tokens. Analyses discovered
tokens for common vulnerabilities: 'none' algorithm acceptance, weak algorithm
choices (RS256→HS256 confusion indicator), empty/missing signature, and structural
anomalies. Educational tool for JWT security awareness.
"""

from __future__ import annotations

import base64
import json
import re
from typing import Any

import httpx
import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()

# JWT pattern: three base64url-encoded segments separated by dots
_JWT_RE = re.compile(r"eyJ[A-Za-z0-9_\-]+\.eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]*")

# Common weak HMAC secrets to check against (offline simulation only)
_WEAK_SECRETS = ["secret", "password", "123456", "changeme", "jwt_secret", "your-256-bit-secret"]

_INSECURE_ALGORITHMS = {"none", "HS256"}


def _b64decode_padding(segment: str) -> bytes:
    """Decode a base64url segment, adding padding as needed."""
    segment += "=" * (4 - len(segment) % 4)
    return base64.urlsafe_b64decode(segment)


def _decode_jwt_parts(token: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str]:
    """Decode JWT header and payload without verification."""
    parts = token.split(".")
    if len(parts) != 3:
        return None, None, ""
    try:
        header = json.loads(_b64decode_padding(parts[0]))
        payload = json.loads(_b64decode_padding(parts[1]))
        signature = parts[2]
        return header, payload, signature
    except Exception:
        return None, None, ""


def _audit_token(token: str) -> dict[str, Any]:
    """Perform static analysis of a JWT token."""
    header, payload, signature = _decode_jwt_parts(token)

    findings: list[str] = []
    severity = "Info"

    if header is None:
        return {"token_preview": token[:30] + "...", "parse_error": True, "findings": [], "severity": "Error"}

    alg = header.get("alg", "").lower()

    if alg == "none":
        findings.append("CRITICAL: Algorithm is 'none' — token is unsigned and trivially forgeable.")
        severity = "Critical"

    if not signature:
        findings.append("HIGH: Empty signature — token lacks cryptographic integrity protection.")
        if severity not in ("Critical",):
            severity = "High"

    if alg == "hs256":
        findings.append(
            "MEDIUM: HS256 (symmetric) algorithm used. If the same key is used for RS256 public-key "
            "verification, an alg-confusion attack may be possible."
        )
        if severity not in ("Critical", "High"):
            severity = "Medium"

    if "exp" not in (payload or {}):
        findings.append("LOW: Token has no 'exp' (expiration) claim — may be a non-expiring token.")
        if severity == "Info":
            severity = "Low"

    kid = header.get("kid")
    if kid and any(c in str(kid) for c in ["'", ";", "--", "/"]):
        findings.append(f"HIGH: 'kid' header contains suspicious characters: {kid} (potential SQLi/path-traversal).")
        if severity not in ("Critical",):
            severity = "High"

    # Obfuscate payload values for privacy
    safe_payload: dict[str, Any] = {}
    for k, v in (payload or {}).items():
        if isinstance(v, str) and len(v) > 20:
            safe_payload[k] = v[:4] + "***"
        else:
            safe_payload[k] = v

    return {
        "token_preview": token[:50] + ("..." if len(token) > 50 else ""),
        "header": header,
        "payload_claims": safe_payload,
        "algorithm": header.get("alg", "unknown"),
        "has_signature": bool(signature),
        "findings": findings,
        "severity": severity,
    }


class JWTSecurityAuditorScanner(BaseOsintScanner):
    """Discovers JWT tokens in target URL responses and audits their security.

    Checks response headers (Authorization, Set-Cookie), body text, and standard
    API response fields. Performs static analysis for 'none' algorithm, missing
    expiration, empty signatures, and alg-confusion indicators (Module 101).
    """

    scanner_name = "jwt_security_auditor"
    supported_input_types = frozenset({ScanInputType.URL})
    cache_ttl = 3600  # 1 hour

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        target = input_value.strip()
        if not target.startswith(("http://", "https://")):
            target = f"https://{target}"

        discovered_tokens: list[str] = []

        async with httpx.AsyncClient(
            timeout=20,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (OSINT-Security-Research/1.0)"},
        ) as client:
            try:
                resp = await client.get(target)
            except httpx.RequestError as exc:
                return {"target": target, "found": False, "error": str(exc)}

            # Search response headers
            for header_name, header_value in resp.headers.items():
                for match in _JWT_RE.finditer(header_value):
                    discovered_tokens.append(match.group(0))

            # Search response body
            for match in _JWT_RE.finditer(resp.text):
                discovered_tokens.append(match.group(0))

            # Deduplicate
            discovered_tokens = list(dict.fromkeys(discovered_tokens))

        audited = [_audit_token(token) for token in discovered_tokens[:10]]

        max_severity = "None"
        severity_order = ["None", "Info", "Low", "Medium", "High", "Critical"]
        for audit in audited:
            s = audit.get("severity", "Info")
            if severity_order.index(s) > severity_order.index(max_severity):
                max_severity = s

        all_findings = [f for a in audited for f in a.get("findings", [])]

        return {
            "target": target,
            "found": len(discovered_tokens) > 0,
            "tokens_found": len(discovered_tokens),
            "tokens_audited": audited,
            "vulnerabilities_found": len(all_findings),
            "highest_severity": max_severity,
            "all_findings": all_findings,
            "educational_note": (
                "JWT vulnerabilities — particularly 'none' algorithm and weak secrets — "
                "allow attackers to forge tokens, escalate privileges, or bypass authentication "
                "entirely. Always verify the 'alg' claim server-side before accepting a token."
            ),
        }
