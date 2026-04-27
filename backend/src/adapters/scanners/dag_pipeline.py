"""DAG-based scanner execution pipeline.

Defines dependency relationships between scanners so that scanners which
consume the output of others run only after their dependencies complete.

Example dependency: httpx_probe_scanner must run after subdomain_scanner
because httpx uses the discovered subdomains as targets.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any
from uuid import UUID

import structlog

from src.core.domain.entities.types import ScanInputType

log = structlog.get_logger(__name__)

# Scanner dependency graph: scanner_name -> set of scanner names it depends on
SCANNER_DEPENDENCIES: dict[str, set[str]] = {
    "httpx_probe_scanner": {"subdomain_scanner", "subfinder_scanner", "amass_scanner", "dnsx_scanner"},
    "nuclei_scanner": {"httpx_probe_scanner"},
    "banner_grabber_scanner": {"shodan_scanner"},
    "subdomain_takeover_scanner": {"subdomain_scanner", "subfinder_scanner", "dnsx_scanner"},
    "cert_scanner": {"subdomain_scanner"},
    "favicon_scanner": {"httpx_probe_scanner"},
    "common_files_scanner": {"httpx_probe_scanner"},
    "waf_scanner": {"httpx_probe_scanner"},
    "tracking_scanner": {"httpx_probe_scanner"},
    "breach_scanner": {"holehe_scanner"},
}


def topological_sort(scanner_names: list[str]) -> list[list[str]]:
    """Return scanners grouped into execution phases based on DAG dependencies.

    Scanners within the same phase have no dependencies on each other and
    can run in parallel.  Phases must run sequentially.

    Args:
        scanner_names: The scanners to order.

    Returns:
        A list of phases, where each phase is a list of scanner names
        that can run concurrently.
    """
    # Only consider dependencies that are in our set
    names_set = set(scanner_names)
    in_phase = {n: set(SCANNER_DEPENDENCIES.get(n, set()) & names_set) for n in scanner_names}
    phases: list[list[str]] = []
    remaining = set(scanner_names)

    while remaining:
        # Scanners whose dependencies have all been scheduled
        ready = sorted(n for n in remaining if not in_phase[n])
        if not ready:
            # Cycle detected — raise so the caller can handle it explicitly
            cycle_nodes = sorted(remaining)
            log.error("scanner_dag_cycle_detected", nodes=cycle_nodes)
            raise ValueError(
                f"Circular dependency detected in scanner DAG involving: {cycle_nodes}"
            )
        phases.append(ready)
        for n in ready:
            remaining.discard(n)
            # Remove this scanner from dependents
            for dep_set in in_phase.values():
                dep_set.discard(n)

    return phases


_DEFAULT_MAX_RETRIES = 2
_DEFAULT_RETRY_BASE_DELAY = 1.0   # seconds
_DEFAULT_RETRY_MAX_DELAY = 30.0   # seconds


async def _run_with_retry(
    scanner_name: str,
    run_scanner_fn: Any,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    base_delay: float = _DEFAULT_RETRY_BASE_DELAY,
    max_delay: float = _DEFAULT_RETRY_MAX_DELAY,
) -> Any:
    """Run a single scanner with exponential-backoff retry on transient failures.

    Permanent failures (auth errors, quota exceeded) are not retried.
    """
    import random

    from src.adapters.scanners.exceptions import ScanAuthError, ScannerQuotaExceededError

    attempt = 0
    last_exc: Exception | None = None

    while attempt <= max_retries:
        try:
            return await run_scanner_fn(scanner_name)
        except (ScanAuthError, ScannerQuotaExceededError):
            # Permanent — don't retry
            raise
        except Exception as exc:
            last_exc = exc
            if attempt == max_retries:
                break
            delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
            log.warning(
                "dag_scanner_retry",
                scanner=scanner_name,
                attempt=attempt + 1,
                retry_in=round(delay, 2),
                error=str(exc),
            )
            await asyncio.sleep(delay)
            attempt += 1

    raise last_exc  # type: ignore[misc]


async def run_dag_pipeline(
    scanner_names: list[str],
    run_scanner_fn: Any,  # async callable(scanner_name) -> ScanResult
    max_retries: int = _DEFAULT_MAX_RETRIES,
    retry_base_delay: float = _DEFAULT_RETRY_BASE_DELAY,
) -> dict[str, Any]:
    """Run scanners in dependency order, parallelising within each phase.

    Each scanner is wrapped in exponential-backoff retry logic so transient
    failures (network hiccups, brief rate limits) don't abort the whole phase.
    Permanent failures (auth, quota) propagate immediately.

    Args:
        scanner_names: Names of scanners to run.
        run_scanner_fn: Async callable that runs one scanner and returns its result.
        max_retries: Per-node retry attempts before giving up (default 2).
        retry_base_delay: Base delay in seconds for the first retry (default 1 s).

    Returns:
        Mapping of scanner_name -> result (None on unrecoverable failure).
    """
    phases = topological_sort(scanner_names)
    results: dict[str, Any] = {}

    for phase_idx, phase in enumerate(phases):
        log.info("dag_phase_start", phase=phase_idx, scanners=phase)
        phase_tasks = [
            _run_with_retry(name, run_scanner_fn, max_retries=max_retries, base_delay=retry_base_delay)
            for name in phase
        ]
        phase_results = await asyncio.gather(*phase_tasks, return_exceptions=True)

        for scanner_name, result in zip(phase, phase_results, strict=True):
            if isinstance(result, Exception):
                log.error("dag_scanner_failed", scanner=scanner_name, error=str(result))
                results[scanner_name] = None
            else:
                results[scanner_name] = result

        log.info("dag_phase_complete", phase=phase_idx, scanners=phase)

    return results
