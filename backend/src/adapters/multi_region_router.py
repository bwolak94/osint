"""Multi-region scanner routing for geographic worker affinity."""

import re
from dataclasses import dataclass, field
from enum import StrEnum
from urllib.parse import urlparse

import structlog

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Region definitions
# ---------------------------------------------------------------------------


class Region(StrEnum):
    US_EAST = "us-east"
    US_WEST = "us-west"
    EU_WEST = "eu-west"
    EU_CENTRAL = "eu-central"
    AP_EAST = "ap-east"
    DEFAULT = "default"


@dataclass
class RegionConfig:
    """Geographic routing configuration for a single worker region."""

    name: Region
    celery_queue: str  # Base queue name, e.g. "light-us-east"
    preferred_tlds: list[str]  # e.g. [".us", ".gov", ".mil"]
    preferred_asns: list[str]  # e.g. ["AS15169"]
    blocked_targets: list[str]  # glob-style patterns for prohibited targets


# ---------------------------------------------------------------------------
# Region configuration registry
# ---------------------------------------------------------------------------

REGION_CONFIGS: dict[Region, RegionConfig] = {
    Region.US_EAST: RegionConfig(
        name=Region.US_EAST,
        celery_queue="light-us-east",
        preferred_tlds=[".us", ".gov", ".mil", ".edu"],
        preferred_asns=[],
        blocked_targets=[],
    ),
    Region.US_WEST: RegionConfig(
        name=Region.US_WEST,
        celery_queue="light-us-west",
        preferred_tlds=[".us", ".gov", ".mil", ".edu"],
        preferred_asns=[],
        blocked_targets=[],
    ),
    Region.EU_WEST: RegionConfig(
        name=Region.EU_WEST,
        celery_queue="light-eu-west",
        preferred_tlds=[".eu", ".uk", ".de", ".fr", ".nl", ".be"],
        preferred_asns=[],
        blocked_targets=[],
    ),
    Region.EU_CENTRAL: RegionConfig(
        name=Region.EU_CENTRAL,
        celery_queue="light-eu-central",
        preferred_tlds=[".pl", ".cz", ".sk", ".hu", ".ro"],
        preferred_asns=[],
        blocked_targets=[],
    ),
    Region.AP_EAST: RegionConfig(
        name=Region.AP_EAST,
        celery_queue="light-ap-east",
        preferred_tlds=[".jp", ".kr", ".cn", ".sg", ".au"],
        preferred_asns=[],
        blocked_targets=[],
    ),
    Region.DEFAULT: RegionConfig(
        name=Region.DEFAULT,
        celery_queue="light",
        preferred_tlds=[],
        preferred_asns=[],
        blocked_targets=[],
    ),
}

# Task-type prefixes used to construct heavy-worker queue names.
_TASK_TYPE_PREFIXES: dict[str, str] = {
    "light": "",   # no prefix needed — queue name already starts with "light-"
    "heavy": "heavy",
}


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


class MultiRegionRouter:
    """Route scan tasks to the optimal geographic worker queue.

    Region selection is based on the TLD of the scan target.  If no region
    matches the TLD the :attr:`Region.DEFAULT` fallback is used.

    Args:
        preferred_regions: When provided, these regions are tried first before
            falling back to TLD-based detection.  Useful for tenants that want
            all their scans pinned to specific geographic workers.
    """

    def __init__(self, preferred_regions: list[Region] | None = None) -> None:
        self._preferred = preferred_regions or [Region.DEFAULT]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def select_region(self, target: str, input_type: str) -> Region:
        """Select the best :class:`Region` for *target*.

        Steps:

        1. Extract the TLD from the target string.
        2. Find the first region whose ``preferred_tlds`` contains the TLD.
        3. If no match, return :attr:`Region.DEFAULT`.

        Args:
            target:     The scan target (domain, URL, IP, …).
            input_type: Hint about target format (``"domain"``, ``"url"``,
                ``"ip"``, etc.).  Currently used only for logging.
        """
        tld = self._extract_tld(target)

        for region, config in REGION_CONFIGS.items():
            if region is Region.DEFAULT:
                continue
            if tld and tld in config.preferred_tlds:
                log.debug(
                    "router.region_selected",
                    target=target,
                    tld=tld,
                    region=region,
                    input_type=input_type,
                )
                return region

        log.debug(
            "router.region_default",
            target=target,
            tld=tld or "<none>",
            input_type=input_type,
        )
        return Region.DEFAULT

    def get_queue(
        self, target: str, input_type: str, task_type: str = "light"
    ) -> str:
        """Return the Celery queue name for *target*.

        The *task_type* argument distinguishes lightweight I/O-bound scanners
        (``"light"``) from CPU/memory-intensive ones (``"heavy"``).  Heavy
        queues are named by replacing the ``light`` prefix with ``heavy``.

        Args:
            target:     Scan target string.
            input_type: Hint about target format.
            task_type:  ``"light"`` (default) or ``"heavy"``.

        Returns:
            A Celery queue name such as ``"light-eu-central"`` or
            ``"heavy-us-east"``.
        """
        region = self.select_region(target, input_type)
        base_queue = REGION_CONFIGS[region].celery_queue

        if task_type == "heavy":
            queue = base_queue.replace("light", "heavy", 1)
        else:
            queue = base_queue

        if not self.is_target_allowed(target, region):
            log.warning(
                "router.target_blocked",
                target=target,
                region=region,
                fallback="light",
            )
            return REGION_CONFIGS[Region.DEFAULT].celery_queue

        log.debug("router.queue_selected", target=target, queue=queue, task_type=task_type)
        return queue

    def is_target_allowed(self, target: str, region: Region) -> bool:
        """Return ``True`` when *target* is not on the region's blocklist.

        Patterns in :attr:`RegionConfig.blocked_targets` are matched as
        case-insensitive glob-style patterns (``*`` matches any substring).
        """
        config = REGION_CONFIGS.get(region)
        if config is None or not config.blocked_targets:
            return True

        lowered = target.lower()
        for pattern in config.blocked_targets:
            # Convert glob wildcard to regex for flexible matching.
            regex = re.escape(pattern).replace(r"\*", ".*")
            if re.search(regex, lowered, re.IGNORECASE):
                log.warning(
                    "router.target_blocked_pattern",
                    target=target,
                    region=region,
                    pattern=pattern,
                )
                return False

        return True

    def suggest_regions(self, investigation_seeds: list[str]) -> dict[Region, int]:
        """Analyse all seeds and return a region-frequency distribution.

        The result is useful for capacity planning: a distribution heavily
        skewed toward ``eu-central`` suggests provisioning additional workers
        in that region before the investigation starts.

        Args:
            investigation_seeds: List of raw target strings (domains, URLs, …).

        Returns:
            A ``{Region: count}`` dict ordered by count (descending).
        """
        distribution: dict[Region, int] = {}

        for seed in investigation_seeds:
            # Use a neutral input_type hint; only TLD matters for region selection.
            region = self.select_region(seed, input_type="seed")
            distribution[region] = distribution.get(region, 0) + 1

        ordered = dict(
            sorted(distribution.items(), key=lambda kv: kv[1], reverse=True)
        )

        log.info(
            "router.region_distribution",
            seeds_count=len(investigation_seeds),
            distribution={k: v for k, v in ordered.items()},
        )
        return ordered

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_tld(self, target: str) -> str:
        """Extract the TLD (including the leading dot) from *target*.

        Handles plain domains, full URLs, and IP addresses.  Returns an empty
        string when no TLD can be determined (e.g. bare IPv4 addresses).

        Examples::

            "example.co.uk"         → ".uk"
            "https://gov.pl/path"   → ".pl"
            "192.168.1.1"           → ""
            "sub.domain.example.eu" → ".eu"
        """
        # Strip scheme so that URL parsing works on plain domains too.
        raw = target.strip()
        if "://" not in raw:
            raw = "https://" + raw

        try:
            parsed = urlparse(raw)
            hostname = parsed.hostname or ""
        except Exception:  # noqa: BLE001
            hostname = ""

        if not hostname:
            return ""

        # Ignore raw IP addresses — they have no TLD.
        ip_pattern = re.compile(
            r"^\d{1,3}(\.\d{1,3}){3}$"  # IPv4
            r"|^\[?[0-9a-fA-F:]+\]?$"   # IPv6
        )
        if ip_pattern.match(hostname):
            return ""

        parts = hostname.split(".")
        if len(parts) < 2:  # noqa: PLR2004
            return ""

        return "." + parts[-1].lower()
