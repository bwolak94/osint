"""Scanner Prometheus metrics — histogram for scan duration, counters for CB state."""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Any

# ---------------------------------------------------------------------------
# In-process histogram implementation (no external prometheus_client required)
# Buckets: 0.5s, 1s, 2s, 5s, 10s, 30s, 60s, +Inf
# ---------------------------------------------------------------------------

_DURATION_BUCKETS = (0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0)

_lock = threading.Lock()

# {scanner_name: {bucket_le: count}}
_duration_buckets: dict[str, dict[float, int]] = defaultdict(lambda: {b: 0 for b in _DURATION_BUCKETS})
_duration_sum: dict[str, float] = defaultdict(float)
_duration_count: dict[str, int] = defaultdict(int)


def record_scan_duration(scanner_name: str, duration_seconds: float) -> None:
    """Record a completed scan duration into the histogram."""
    with _lock:
        _duration_sum[scanner_name] += duration_seconds
        _duration_count[scanner_name] += 1
        for bucket in _DURATION_BUCKETS:
            if duration_seconds <= bucket:
                _duration_buckets[scanner_name][bucket] += 1


def prometheus_histogram_text() -> str:
    """Render scanner duration histogram in Prometheus exposition format."""
    lines: list[str] = [
        "# HELP osint_scanner_duration_seconds Duration of OSINT scanner executions",
        "# TYPE osint_scanner_duration_seconds histogram",
    ]
    with _lock:
        for scanner, buckets in _duration_buckets.items():
            cumulative = 0
            for le in _DURATION_BUCKETS:
                cumulative += buckets[le]
                lines.append(
                    f'osint_scanner_duration_seconds_bucket{{scanner="{scanner}",le="{le}"}} {cumulative}'
                )
            lines.append(
                f'osint_scanner_duration_seconds_bucket{{scanner="{scanner}",le="+Inf"}} {_duration_count[scanner]}'
            )
            lines.append(
                f'osint_scanner_duration_seconds_sum{{scanner="{scanner}"}} {_duration_sum[scanner]:.4f}'
            )
            lines.append(
                f'osint_scanner_duration_seconds_count{{scanner="{scanner}"}} {_duration_count[scanner]}'
            )
    return "\n".join(lines)
