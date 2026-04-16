"""Maigret scanner — checks username across 3000+ sites using the maigret Python library."""

import asyncio
import os
from typing import Any

import structlog

from src.adapters.scanners.base import BaseOsintScanner
from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger()


class MaigretScanner(BaseOsintScanner):
    """Checks username presence across 3000+ websites using Maigret.

    Uses the maigret Python library directly for searching.
    Many sites may return false negatives from Docker/server IPs
    due to anti-bot protections.
    """

    scanner_name = "maigret"
    supported_input_types = frozenset({ScanInputType.USERNAME})

    async def _do_scan(self, input_value: str, input_type: ScanInputType) -> dict[str, Any]:
        try:
            import maigret as maigret_pkg
            from maigret.sites import MaigretDatabase
            from maigret import search
            from maigret.result import MaigretCheckStatus
            import logging

            # Load database
            db = MaigretDatabase()
            pkg_dir = os.path.dirname(maigret_pkg.__file__)
            data_file = os.path.join(pkg_dir, "resources", "data.json")
            db.load_from_path(data_file)

            logger = logging.getLogger("maigret")
            logger.setLevel(logging.ERROR)

            sites = db.sites_dict

            # Run the search
            results = await search(
                input_value,
                sites,
                logger,
                timeout=15,
                no_progressbar=True,
                max_connections=50,
                retries=1,
            )

            # Extract claimed profiles
            claimed_profiles = []
            for site_name, result in results.items():
                status = result.get("status")
                if status == MaigretCheckStatus.CLAIMED:
                    claimed_profiles.append({
                        "site": site_name,
                        "url": result.get("url_user", ""),
                    })

            return {
                "username": input_value,
                "claimed_profiles": claimed_profiles,
                "claimed_count": len(claimed_profiles),
                "total_checked": len(results),
                "extracted_identifiers": self._build_identifiers(claimed_profiles),
            }

        except ImportError as e:
            log.warning("maigret not available", error=str(e))
            return {
                "username": input_value,
                "claimed_profiles": [],
                "claimed_count": 0,
                "total_checked": 0,
                "extracted_identifiers": [],
                "_stub": True,
            }
        except Exception as e:
            log.error("maigret scan error", error=str(e))
            raise

    def _build_identifiers(self, profiles: list[dict[str, Any]]) -> list[str]:
        identifiers: list[str] = []
        for p in profiles:
            url = p.get("url", "")
            if url:
                identifiers.append(f"url:{url}")
            site = p.get("site", "")
            if site:
                identifiers.append(f"service:{site}")
        return identifiers
