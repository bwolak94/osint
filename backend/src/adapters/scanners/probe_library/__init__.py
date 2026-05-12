"""Probe template library — aggregates all built-in ProbeTemplates.

Import `all_templates()` to get the full list. Each category module
exposes a `TEMPLATES: list[ProbeTemplate]` at module level.
"""

from __future__ import annotations

from src.adapters.scanners.probe_template import ProbeTemplate

from .exposed_files import TEMPLATES as _EXPOSED_FILES
from .misconfiguration import TEMPLATES as _MISCONFIGURATION
from .security_headers import TEMPLATES as _SECURITY_HEADERS
from .tls_checks import TEMPLATES as _TLS_CHECKS
from .web_tech import TEMPLATES as _WEB_TECH

_ALL: list[ProbeTemplate] | None = None


def all_templates() -> list[ProbeTemplate]:
    """Return all registered probe templates (cached singleton list)."""
    global _ALL
    if _ALL is None:
        _ALL = [
            *_SECURITY_HEADERS,
            *_EXPOSED_FILES,
            *_MISCONFIGURATION,
            *_WEB_TECH,
            *_TLS_CHECKS,
        ]
    return _ALL


def templates_by_category(category: str) -> list[ProbeTemplate]:
    return [t for t in all_templates() if t.category == category]


def templates_by_severity(severity: str) -> list[ProbeTemplate]:
    return [t for t in all_templates() if t.severity.value == severity]


__all__ = ["all_templates", "templates_by_category", "templates_by_severity"]
