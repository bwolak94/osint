"""Maigret scanner — checks username across 3000+ sites."""

import asyncio
import json
import os
import tempfile
from typing import Any
from uuid import uuid4

import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.adapters.scanners.exceptions import ScanTimeoutError
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()


class MaigretScanner(BaseOsintScanner):
    """Checks username presence across 3000+ websites using Maigret CLI.

    Runs as a subprocess with a 120-second timeout. Results are parsed
    from the JSON output file.
    """

    scanner_name = "maigret"
    supported_input_types = frozenset({ScanInputType.USERNAME})

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._timeout = 120

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        output_file = os.path.join(tempfile.gettempdir(), f"maigret_{uuid4().hex}.json")

        try:
            proc = await asyncio.create_subprocess_exec(
                "maigret", input_value,
                "--json", "simple",
                "-o", output_file,
                "--timeout", "30",
                "--retries", "1",
                "--no-color",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self._timeout)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                raise ScanTimeoutError(f"Maigret scan timed out after {self._timeout}s")

            # Parse JSON output
            results = self._parse_output(output_file)
            claimed_profiles = [r for r in results if r.get("status", "").lower() == "claimed"]

            return {
                "username": input_value,
                "claimed_profiles": [
                    {"site": p.get("site_name", ""), "url": p.get("url_user", "")}
                    for p in claimed_profiles
                ],
                "claimed_count": len(claimed_profiles),
                "total_checked": len(results),
                "extracted_identifiers": self._build_identifiers(claimed_profiles),
            }
        finally:
            if os.path.exists(output_file):
                os.unlink(output_file)

    def _parse_output(self, output_file: str) -> list[dict[str, Any]]:
        if not os.path.exists(output_file):
            return []
        try:
            with open(output_file) as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return list(data.values()) if data else []
            return []
        except (json.JSONDecodeError, OSError):
            return []

    def _build_identifiers(self, profiles: list[dict[str, Any]]) -> list[str]:
        identifiers: list[str] = []
        for p in profiles:
            url = p.get("url_user", "") or p.get("url", "")
            if url:
                identifiers.append(f"url:{url}")
            site = p.get("site_name", "") or p.get("site", "")
            if site:
                identifiers.append(f"service:{site}")
        return identifiers
