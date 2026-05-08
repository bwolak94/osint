"""WorldMonitor background scheduler.

Uses a simple asyncio task loop (no extra APScheduler dependency).
Runs the RSS aggregator every RSS_INTERVAL_S seconds.
Lifecycle is tied to the FastAPI app lifespan via start() / stop().
"""

from __future__ import annotations

import asyncio
from typing import Any

import redis.asyncio as aioredis
import structlog

from .rss_aggregator import run_aggregation

log = structlog.get_logger(__name__)

RSS_INTERVAL_S = 300  # 5 minutes


class WorldMonitorScheduler:
    """Owns all WorldMonitor background tasks."""

    def __init__(self) -> None:
        self._tasks: list[asyncio.Task[Any]] = []
        self._running = False

    async def start(self, redis: aioredis.Redis) -> None:
        if self._running:
            return
        self._running = True
        log.info("worldmonitor_scheduler_start")

        # Run immediately on startup, then on interval
        self._tasks.append(asyncio.create_task(self._rss_loop(redis), name="wm-rss-loop"))

    async def stop(self) -> None:
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        log.info("worldmonitor_scheduler_stop")

    async def _rss_loop(self, redis: aioredis.Redis) -> None:
        """Fetch RSS feeds immediately, then repeat every RSS_INTERVAL_S seconds."""
        while self._running:
            try:
                await run_aggregation(redis)
            except Exception as exc:
                log.error("rss_aggregation_error", error=str(exc))
            if not self._running:
                break
            await asyncio.sleep(RSS_INTERVAL_S)


# Singleton — imported by the FastAPI lifespan
scheduler = WorldMonitorScheduler()
