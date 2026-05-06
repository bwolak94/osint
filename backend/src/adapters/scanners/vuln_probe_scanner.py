"""VulnProbeScanner — template-driven vulnerability and misconfiguration detection.

Own implementation of a probe-based web security scanner. Unlike the existing
NucleiScanner (which wraps the nuclei binary), this scanner is entirely
self-contained: templates are typed Python dataclasses, the execution engine
is async-native, and results integrate directly with the graph via structured
identifiers.

Architecture:
    ProbeTemplate (probe_template.py)  — immutable template data model
    ProbeEngine   (probe_engine.py)    — stateless async executor
    probe_library (probe_library/)     — curated built-in template catalogue
    VulnProbeScanner (this file)       — BaseOsintScanner adapter

Supported input types:
    DOMAIN  — scanned as https://<domain>
    URL     — scanned as-is
    IP_ADDRESS — scanned as http://<ip>
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any
from urllib.parse import urlparse

import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.adapters.scanners.probe_engine import ProbeEngine, ProbeResult
from src.adapters.scanners.probe_library import all_templates
from src.adapters.scanners.probe_template import Severity
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger(__name__)

# Severity → numeric rank for sorting / confidence weighting
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.CRITICAL: 5,
    Severity.HIGH: 4,
    Severity.MEDIUM: 3,
    Severity.LOW: 2,
    Severity.INFO: 1,
}

# Confidence contribution per severity level (how much a finding raises overall confidence)
_SEVERITY_CONFIDENCE: dict[Severity, float] = {
    Severity.CRITICAL: 0.20,
    Severity.HIGH: 0.12,
    Severity.MEDIUM: 0.07,
    Severity.LOW: 0.03,
    Severity.INFO: 0.01,
}


class VulnProbeScanner(BaseOsintScanner):
    """Template-driven web security probe scanner.

    Runs all built-in ProbeTemplates against the target concurrently.
    Each matched finding is converted into a structured vulnerability record
    and exposed as a graph identifier for the investigation graph.

    Result shape::

        {
          "target_url": str,
          "input": str,
          "scan_mode": "template_engine",
          "findings": [ { template_id, name, severity, category, ... }, ... ],
          "findings_by_severity": { "critical": [...], "high": [...], ... },
          "summary": { "critical": int, "high": int, ... },
          "templates_run": int,
          "elapsed_ms": int,
          "extracted_identifiers": [ "vulnerability:<severity>:<template_id>", ... ],
        }
    """

    scanner_name = "vuln_probe"
    supported_input_types = frozenset({
        ScanInputType.DOMAIN,
        ScanInputType.URL,
        ScanInputType.IP_ADDRESS,
    })
    cache_ttl = 3600        # 1 hour
    scan_timeout = 120      # 2 minutes hard limit
    source_confidence = 0.8

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._engine = ProbeEngine(concurrency=20)

    # ── Core scan ─────────────────────────────────────────────────────────────

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        target_url = _normalize_target(input_value, input_type)
        templates = all_templates()

        log.info(
            "vuln_probe_start",
            target=target_url,
            templates=len(templates),
        )

        engine_result = await self._engine.run_all(templates, target_url)

        findings = sorted(
            engine_result.findings,
            key=lambda f: _SEVERITY_RANK.get(f.severity, 0),
            reverse=True,
        )

        by_severity = _group_by_severity(findings)
        summary = {sev: len(items) for sev, items in by_severity.items()}
        identifiers = _build_identifiers(findings, target_url)

        log.info(
            "vuln_probe_done",
            target=target_url,
            total_findings=len(findings),
            critical=summary.get("critical", 0),
            high=summary.get("high", 0),
            medium=summary.get("medium", 0),
            elapsed_ms=engine_result.elapsed_ms,
        )

        return {
            "target_url": target_url,
            "input": input_value,
            "scan_mode": "template_engine",
            "findings": [_finding_to_dict(f) for f in findings],
            "findings_by_severity": {
                sev: [_finding_to_dict(f) for f in items]
                for sev, items in by_severity.items()
            },
            "summary": summary,
            "templates_run": engine_result.total_templates,
            "elapsed_ms": engine_result.elapsed_ms,
            "engine_errors": engine_result.errors[:10],  # cap to avoid huge payloads
            "extracted_identifiers": identifiers,
        }

    # ── Identifier extraction ─────────────────────────────────────────────────

    def _extract_identifiers(self, raw_data: dict[str, Any]) -> list[str]:
        return raw_data.get("extracted_identifiers", [])

    def _compute_confidence(self, raw_data: dict[str, Any], extracted: list[str]) -> float:
        if raw_data.get("_stub") or raw_data.get("_not_found"):
            return 0.0
        findings = raw_data.get("findings", [])
        if not findings:
            return round(self.source_confidence * 0.15, 4)  # ran clean — low but non-zero

        # Accumulate confidence contribution per finding (capped at 0.95)
        confidence = 0.15  # base: scan ran successfully
        for f in findings:
            sev = Severity(f.get("severity", "info"))
            confidence += _SEVERITY_CONFIDENCE.get(sev, 0.01)
        return round(min(0.95, confidence), 4)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalize_target(value: str, input_type: ScanInputType) -> str:
    """Return a fully-qualified URL for the given input."""
    value = value.strip()
    if input_type == ScanInputType.IP_ADDRESS:
        return f"http://{value}"
    if input_type == ScanInputType.DOMAIN:
        return f"https://{value}"
    # URL — ensure it has a scheme
    if not value.startswith(("http://", "https://")):
        return f"https://{value}"
    return value


def _group_by_severity(findings: list[ProbeResult]) -> dict[str, list[ProbeResult]]:
    groups: dict[str, list[ProbeResult]] = {
        "critical": [],
        "high": [],
        "medium": [],
        "low": [],
        "info": [],
    }
    for f in findings:
        groups.setdefault(f.severity.value, []).append(f)
    return groups


def _finding_to_dict(f: ProbeResult) -> dict[str, Any]:
    return {
        "template_id": f.template_id,
        "name": f.name,
        "severity": f.severity.value,
        "category": f.category,
        "description": f.description,
        "matched_at": f.matched_at,
        "evidence": f.evidence[:300],  # keep payload size manageable
        "extracted": f.extracted,
        "request_ms": f.request_ms,
        "remediation": f.remediation,
        "references": list(f.references),
        "cvss_score": f.cvss_score,
        "tags": list(f.tags),
    }


def _build_identifiers(findings: list[ProbeResult], target_url: str) -> list[str]:
    ids: list[str] = [f"url:{target_url}"]
    seen: set[str] = set()
    for f in findings:
        vuln_id = f"vulnerability:{f.severity.value}:{f.template_id}"
        if vuln_id not in seen:
            ids.append(vuln_id)
            seen.add(vuln_id)
        url_id = f"url:{f.matched_at}"
        if url_id not in seen and f.matched_at != target_url:
            ids.append(url_id)
            seen.add(url_id)
    return ids
