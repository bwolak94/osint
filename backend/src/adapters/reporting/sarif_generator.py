"""SARIF 2.1.0 report generator for PentAI findings.

Converts a list of PentestFindingModel objects into a SARIF 2.1.0 JSON document
suitable for import into GitHub Advanced Security, Azure DevOps, or any
SARIF-compatible viewer.

Reference: https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import structlog

log = structlog.get_logger(__name__)

_SARIF_SCHEMA = (
    "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json"
)
_TOOL_NAME = "PentAI"
_TOOL_VERSION = "1.0.0"
_TOOL_INFO_URL = "https://github.com/pentai/pentai"

# Severity → SARIF result level mapping
_SEVERITY_TO_LEVEL: dict[str, str] = {
    "critical": "error",
    "high": "error",
    "medium": "warning",
    "low": "note",
    "info": "none",
}

# SARIF result kind values
_SEVERITY_TO_KIND: dict[str, str] = {
    "critical": "fail",
    "high": "fail",
    "medium": "fail",
    "low": "open",
    "info": "informational",
}


class SarifGenerator:
    """Generates a SARIF 2.1.0 document from PentestFindingModel instances."""

    def generate(self, findings: list[Any], scan_id: str | None = None) -> dict[str, Any]:
        """Build the full SARIF document.

        Args:
            findings: List of PentestFindingModel ORM instances.
            scan_id: Optional scan UUID string, added to run properties.

        Returns:
            Python dict representing the SARIF document (JSON-serialisable).
        """
        rules = self._build_rules(findings)
        results = [self._finding_to_result(f) for f in findings]

        run: dict[str, Any] = {
            "tool": {
                "driver": {
                    "name": _TOOL_NAME,
                    "version": _TOOL_VERSION,
                    "informationUri": _TOOL_INFO_URL,
                    "rules": rules,
                }
            },
            "results": results,
            "properties": {
                "generatedAt": datetime.now(timezone.utc).isoformat(),
            },
        }

        if scan_id:
            run["properties"]["scanId"] = scan_id

        return {
            "$schema": _SARIF_SCHEMA,
            "version": "2.1.0",
            "runs": [run],
        }

    def to_json(self, findings: list[Any], scan_id: str | None = None, indent: int = 2) -> str:
        """Return the SARIF document as a JSON string."""
        return json.dumps(self.generate(findings, scan_id=scan_id), indent=indent, default=str)

    # ------------------------------------------------------------------
    # Rules
    # ------------------------------------------------------------------

    def _build_rules(self, findings: list[Any]) -> list[dict[str, Any]]:
        """Deduplicate and build the SARIF rules array from all findings."""
        seen_rule_ids: set[str] = set()
        rules: list[dict[str, Any]] = []

        for finding in findings:
            rule_id = self._rule_id(finding)
            if rule_id in seen_rule_ids:
                continue
            seen_rule_ids.add(rule_id)
            rules.append(self._finding_to_rule(finding, rule_id))

        return rules

    def _rule_id(self, finding: Any) -> str:
        """Derive a stable rule ID from CWE, wstg_id, or tool+title."""
        if getattr(finding, "cwe", None):
            return f"CWE-{finding.cwe}"
        if getattr(finding, "wstg_id", None):
            return finding.wstg_id
        tool = getattr(finding, "tool", "unknown") or "unknown"
        title_slug = _slugify(getattr(finding, "title", "finding"))
        return f"{tool}/{title_slug}"

    def _finding_to_rule(self, finding: Any, rule_id: str) -> dict[str, Any]:
        severity = (getattr(finding, "severity", None) or "info").lower()
        title = getattr(finding, "title", rule_id)
        description = getattr(finding, "description", None) or title

        rule: dict[str, Any] = {
            "id": rule_id,
            "name": _pascal_case(title),
            "shortDescription": {"text": title},
            "fullDescription": {"text": description},
            "defaultConfiguration": {
                "level": _SEVERITY_TO_LEVEL.get(severity, "warning")
            },
            "properties": {
                "tags": _build_tags(finding),
                "severity": severity,
            },
        }

        # Add CWE help URL
        if getattr(finding, "cwe", None):
            rule["helpUri"] = f"https://cwe.mitre.org/data/definitions/{finding.cwe}.html"
            rule["help"] = {
                "text": f"CWE-{finding.cwe}: See https://cwe.mitre.org/data/definitions/{finding.cwe}.html"
            }

        return rule

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------

    def _finding_to_result(self, finding: Any) -> dict[str, Any]:
        severity = (getattr(finding, "severity", None) or "info").lower()
        rule_id = self._rule_id(finding)
        title = getattr(finding, "title", "Finding")
        description = getattr(finding, "description", None) or title

        # Build evidence text
        evidence: dict[str, Any] = getattr(finding, "evidence", None) or {}
        evidence_text = _format_evidence(evidence)
        message_text = f"{description}\n\n{evidence_text}".strip() if evidence_text else description

        result: dict[str, Any] = {
            "ruleId": rule_id,
            "level": _SEVERITY_TO_LEVEL.get(severity, "warning"),
            "kind": _SEVERITY_TO_KIND.get(severity, "fail"),
            "message": {"text": message_text},
            "properties": {
                "severity": severity,
                "tool": getattr(finding, "tool", None),
                "status": getattr(finding, "status", "new"),
            },
        }

        # Attach CVSS score
        if getattr(finding, "cvss_v3", None):
            result["properties"]["cvssV3"] = float(finding.cvss_v3)

        # Attach CVE IDs
        cve_list = getattr(finding, "cve", None) or []
        if cve_list:
            result["properties"]["cveIds"] = list(cve_list)

        # Attach MITRE techniques
        mitre = getattr(finding, "mitre_techniques", None) or []
        if mitre:
            result["properties"]["mitreTechniques"] = list(mitre)

        # Attach WSTG tags
        wstg_id = getattr(finding, "wstg_id", None)
        if wstg_id:
            result["properties"]["wstgId"] = wstg_id

        # Attach location (host/port/url) if available
        location = self._build_location(finding)
        if location:
            result["locations"] = [location]

        # Attach remediation as a fix suggestion
        remediation = getattr(finding, "remediation", None)
        if remediation:
            result["fixes"] = [
                {
                    "description": {"text": remediation},
                    "artifactChanges": [],
                }
            ]

        return result

    def _build_location(self, finding: Any) -> dict[str, Any] | None:
        target: dict[str, Any] = getattr(finding, "target", None) or {}
        host = target.get("host") or target.get("ip") or ""
        port = target.get("port")
        url = target.get("url") or ""

        if not host and not url:
            return None

        uri = url or f"host://{host}" + (f":{port}" if port else "")
        return {
            "physicalLocation": {
                "artifactLocation": {"uri": uri},
                "region": {"startLine": 1},
            }
        }


# ------------------------------------------------------------------
# Helper utilities
# ------------------------------------------------------------------


def _build_tags(finding: Any) -> list[str]:
    """Collect tags from wstg_id, MITRE techniques, and tool name."""
    tags: list[str] = []
    wstg_id = getattr(finding, "wstg_id", None)
    if wstg_id:
        tags.append(wstg_id)
    mitre = getattr(finding, "mitre_techniques", None) or []
    tags.extend(mitre)
    tool = getattr(finding, "tool", None)
    if tool:
        tags.append(f"tool:{tool}")
    severity = getattr(finding, "severity", None)
    if severity:
        tags.append(f"severity:{severity}")
    return tags


def _format_evidence(evidence: dict[str, Any]) -> str:
    """Format evidence dict as human-readable text for SARIF message."""
    if not evidence:
        return ""
    lines: list[str] = ["Evidence:"]
    for key, value in evidence.items():
        if value is None:
            continue
        # Truncate long hash values for readability
        val_str = str(value)
        if len(val_str) > 120:
            val_str = val_str[:117] + "..."
        lines.append(f"  {key}: {val_str}")
    return "\n".join(lines)


def _slugify(text: str) -> str:
    """Convert a title to a lowercase-hyphenated slug."""
    import re
    text = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[\s_]+", "-", text).strip("-")[:64]


def _pascal_case(text: str) -> str:
    """Convert a title to PascalCase for SARIF rule name."""
    return "".join(word.capitalize() for word in text.split()[:6])
