"""Test Catalog API — serve YAML module definitions to the frontend."""

from __future__ import annotations

import glob
import os
from pathlib import Path
from typing import Any

import structlog
import yaml
from fastapi import APIRouter, HTTPException

log = structlog.get_logger(__name__)
router = APIRouter()

_MODULES_DIR = Path(__file__).parent.parent.parent.parent.parent / "modules"


def _load_modules() -> list[dict[str, Any]]:
    """Load all YAML module files from the modules directory."""
    modules: list[dict[str, Any]] = []
    pattern = str(_MODULES_DIR / "*.yaml")

    for path in sorted(glob.glob(pattern)):
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
                if isinstance(data, dict):
                    data["_file"] = os.path.basename(path)
                    modules.append(data)
        except Exception as exc:
            log.warning("module_load_failed", path=path, error=str(exc))

    return modules


@router.get(
    "/test-catalog",
    summary="List all test catalog modules (YAML definitions)",
)
async def list_modules(
    ptes_phase: str | None = None,
    severity: str | None = None,
    tag: str | None = None,
) -> dict[str, Any]:
    """Return all available pentest module definitions from YAML catalog."""
    modules = _load_modules()

    if ptes_phase:
        modules = [m for m in modules if m.get("ptes_phase") == ptes_phase]
    if severity:
        modules = [m for m in modules if m.get("severity") == severity]
    if tag:
        modules = [m for m in modules if tag in (m.get("tags") or [])]

    return {
        "modules": modules,
        "total": len(modules),
        "phases": list({m.get("ptes_phase", "") for m in modules}),
    }


@router.get(
    "/test-catalog/{module_id}",
    summary="Get a single test catalog module by ID",
)
async def get_module(module_id: int) -> dict[str, Any]:
    """Return a single module definition by its numeric ID."""
    modules = _load_modules()
    for m in modules:
        if m.get("id") == module_id:
            return m
    raise HTTPException(status_code=404, detail=f"Module {module_id} not found")
