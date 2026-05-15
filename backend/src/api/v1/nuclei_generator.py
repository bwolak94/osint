"""Nuclei Template Generator.

Generates Nuclei YAML templates from CVE identifiers or vulnerability
descriptions using heuristic rule mapping and pattern libraries.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.v1.auth.dependencies import get_current_user
from src.core.domain.entities.user import User


from src.config import get_settings as _get_settings

# When OSINT_MOCK_DATA=false, endpoints return 501 — real data source required. (#13)
_MOCK_DATA: bool = _get_settings().osint_mock_data

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/nuclei-generator", tags=["nuclei-generator"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class NucleiTemplate(BaseModel):
    template_id: str
    name: str
    severity: str
    tags: list[str]
    description: str
    yaml_content: str
    cve_id: str | None
    protocol: str  # http, network, dns
    confidence: float
    warnings: list[str]


class TemplateGenerationRequest(BaseModel):
    cve_id: str | None = Field(None, description="CVE identifier (e.g. CVE-2024-12345)")
    vulnerability_title: str = Field(..., min_length=5, description="Vulnerability title or description")
    affected_component: str = Field(..., min_length=2, description="Affected software/component")
    vuln_type: str = Field(
        "rce",
        description="Vulnerability type: rce, sqli, xss, ssrf, lfi, idor, auth_bypass, info_disclosure",
    )
    target_url_pattern: str | None = Field(None, description="Known URL pattern if any")
    cvss_score: float | None = Field(None, ge=0.0, le=10.0)


# ---------------------------------------------------------------------------
# Template generation logic
# ---------------------------------------------------------------------------

_SEVERITY_MAP = {
    (9.0, 10.0): "critical",
    (7.0, 8.9): "high",
    (4.0, 6.9): "medium",
    (0.0, 3.9): "low",
}

_VULN_MATCHERS: dict[str, dict[str, Any]] = {
    "rce": {
        "tags": ["rce", "cve", "oast"],
        "protocol": "http",
        "matcher_type": "word",
        "matcher_words": ["Interactsh"],
        "path_suffix": "/execute",
        "method": "POST",
        "body_template": '{"cmd": "{{interactsh-url}}"}',
        "oast": True,
    },
    "sqli": {
        "tags": ["sqli", "cve", "blind"],
        "protocol": "http",
        "matcher_type": "regex",
        "matcher_regex": r"SQL syntax|mysql_fetch|ORA-[0-9]+|syntax error",
        "path_suffix": "?id=1'",
        "method": "GET",
        "body_template": None,
        "oast": False,
    },
    "xss": {
        "tags": ["xss", "cve"],
        "protocol": "http",
        "matcher_type": "word",
        "matcher_words": ["<script>alert(1)</script>", "xss-probe"],
        "path_suffix": '?q=<script>alert(1)</script>',
        "method": "GET",
        "body_template": None,
        "oast": False,
    },
    "ssrf": {
        "tags": ["ssrf", "cve", "oast"],
        "protocol": "http",
        "matcher_type": "word",
        "matcher_words": ["Interactsh"],
        "path_suffix": "/redirect?url={{interactsh-url}}",
        "method": "GET",
        "body_template": None,
        "oast": True,
    },
    "lfi": {
        "tags": ["lfi", "cve", "file-read"],
        "protocol": "http",
        "matcher_type": "regex",
        "matcher_regex": r"root:.*:0:0:|\\[boot loader\\]",
        "path_suffix": "?file=../../../../etc/passwd",
        "method": "GET",
        "body_template": None,
        "oast": False,
    },
    "idor": {
        "tags": ["idor", "cve", "auth"],
        "protocol": "http",
        "matcher_type": "status",
        "matcher_status": [200],
        "path_suffix": "/api/users/1",
        "method": "GET",
        "body_template": None,
        "oast": False,
    },
    "auth_bypass": {
        "tags": ["auth-bypass", "cve"],
        "protocol": "http",
        "matcher_type": "word",
        "matcher_words": ["admin", "dashboard", "Welcome"],
        "path_suffix": "/admin",
        "method": "GET",
        "body_template": None,
        "oast": False,
    },
    "info_disclosure": {
        "tags": ["exposure", "cve", "info-disclosure"],
        "protocol": "http",
        "matcher_type": "regex",
        "matcher_regex": r"password|secret|api.key|AWS_SECRET|token",
        "path_suffix": "/.env",
        "method": "GET",
        "body_template": None,
        "oast": False,
    },
}


def _get_severity(cvss: float | None, vuln_type: str) -> str:
    if cvss is not None:
        for (low, high), sev in _SEVERITY_MAP.items():
            if low <= cvss <= high:
                return sev
    severity_defaults = {
        "rce": "critical", "sqli": "high", "ssrf": "high",
        "xss": "medium", "lfi": "high", "idor": "medium",
        "auth_bypass": "high", "info_disclosure": "medium",
    }
    return severity_defaults.get(vuln_type, "medium")


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9-]", "-", text.lower())[:60].strip("-")


def _generate_yaml(req: TemplateGenerationRequest, vuln_config: dict[str, Any], severity: str) -> str:
    cve_ref = f"\n    - https://nvd.nist.gov/vuln/detail/{req.cve_id}" if req.cve_id else ""
    component_slug = _slugify(req.affected_component)
    template_id = f"{component_slug}-{req.vuln_type}"
    if req.cve_id:
        template_id = _slugify(req.cve_id)

    path = req.target_url_pattern or ("{{BaseURL}}" + vuln_config["path_suffix"])

    # Build matcher block
    if vuln_config["matcher_type"] == "word":
        words_yaml = "\n".join(f'        - "{w}"' for w in vuln_config["matcher_words"])
        matcher_block = f"""      - type: word
        words:
{words_yaml}"""
    elif vuln_config["matcher_type"] == "regex":
        matcher_block = f"""      - type: regex
        regex:
          - '{vuln_config["matcher_regex"]}'"""
    else:
        status = vuln_config.get("matcher_status", [200])
        status_yaml = "\n".join(f"          - {s}" for s in status)
        matcher_block = f"""      - type: status
        status:
{status_yaml}"""

    body_block = f"\n        body: '{vuln_config['body_template']}'" if vuln_config.get("body_template") else ""
    oast_note = "    # Requires Interactsh (--interactsh-url flag)\n" if vuln_config.get("oast") else ""

    tags_str = ", ".join(vuln_config["tags"])
    refs = f"https://nvd.nist.gov/vuln/detail/{req.cve_id}" if req.cve_id else f"https://example.com/{component_slug}"

    return f"""id: {template_id}

info:
  name: {req.vulnerability_title}
  author: osint-platform
  severity: {severity}
  description: |
    {req.vulnerability_title} affecting {req.affected_component}.
    {f'CVSS Score: {req.cvss_score}' if req.cvss_score else ''}
  reference:
    - {refs}
  tags: {tags_str}
  metadata:
    verified: false
    max-request: 1
{oast_note}
http:
  - method: {vuln_config['method']}
    path:
      - "{path}"
{body_block}

    matchers-condition: and
    matchers:
{matcher_block}

      - type: status
        status:
          - 200
          - 500
        negative: true  # Exclude normal errors
"""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/generate", response_model=NucleiTemplate)
async def generate_template(
    body: TemplateGenerationRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> NucleiTemplate:
    """Generate a Nuclei YAML template from vulnerability details."""
    vuln_config = _VULN_MATCHERS.get(body.vuln_type)
    if not vuln_config:
        raise HTTPException(400, f"Unsupported vulnerability type: {body.vuln_type}. Supported: {list(_VULN_MATCHERS)}")

    severity = _get_severity(body.cvss_score, body.vuln_type)
    yaml_content = _generate_yaml(body, vuln_config, severity)
    component_slug = _slugify(body.affected_component)
    template_id = _slugify(body.cve_id) if body.cve_id else f"{component_slug}-{body.vuln_type}"

    warnings: list[str] = []
    if not body.target_url_pattern:
        warnings.append("No target URL pattern provided — path suffix is a best-guess heuristic")
    if not body.cve_id:
        warnings.append("No CVE ID — template references and fingerprinting may be imprecise")
    if vuln_config.get("oast"):
        warnings.append("Template requires Interactsh OOB server (--interactsh-url)")

    confidence = 0.8 if body.cve_id and body.target_url_pattern else 0.6 if body.cve_id else 0.4
    log.info("nuclei_template_generated", template_id=template_id, vuln_type=body.vuln_type, severity=severity)

    return NucleiTemplate(
        template_id=template_id,
        name=body.vulnerability_title,
        severity=severity,
        tags=vuln_config["tags"],
        description=f"{body.vulnerability_title} — {body.affected_component}",
        yaml_content=yaml_content,
        cve_id=body.cve_id,
        protocol=vuln_config["protocol"],
        confidence=confidence,
        warnings=warnings,
    )


@router.get("/supported-types", response_model=list[dict[str, str]])
async def list_supported_types(
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[dict[str, str]]:
    """List all supported vulnerability types for template generation."""
    if not _MOCK_DATA:
        raise HTTPException(status_code=501, detail="Real data source not configured — set OSINT_MOCK_DATA=true or wire up a live integration.")
    descriptions = {
        "rce": "Remote Code Execution",
        "sqli": "SQL Injection",
        "xss": "Cross-Site Scripting",
        "ssrf": "Server-Side Request Forgery",
        "lfi": "Local File Inclusion",
        "idor": "Insecure Direct Object Reference",
        "auth_bypass": "Authentication Bypass",
        "info_disclosure": "Information Disclosure",
    }
    return [{"type": k, "description": v} for k, v in descriptions.items()]
