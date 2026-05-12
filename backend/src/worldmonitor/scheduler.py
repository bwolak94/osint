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

from .events_aggregator import run_events_aggregation
from .rss_aggregator import run_aggregation
from .social_scraper import run_social_aggregation

log = structlog.get_logger(__name__)

RSS_INTERVAL_S = 300     # 5 minutes
EVENTS_INTERVAL_S = 600  # 10 minutes
SOCIAL_INTERVAL_S = 300  # 5 minutes


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

        self._tasks.append(asyncio.create_task(self._rss_loop(redis), name="wm-rss-loop"))
        self._tasks.append(asyncio.create_task(self._events_loop(redis), name="wm-events-loop"))
        self._tasks.append(asyncio.create_task(self._social_loop(redis), name="wm-social-loop"))

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

    async def _events_loop(self, redis: aioredis.Redis) -> None:
        """Fetch geospatial events immediately, then repeat every EVENTS_INTERVAL_S seconds."""
        while self._running:
            try:
                await run_events_aggregation(redis)
            except Exception as exc:
                log.error("events_aggregation_error", error=str(exc))
            if not self._running:
                break
            await asyncio.sleep(EVENTS_INTERVAL_S)

    async def _social_loop(self, redis: aioredis.Redis) -> None:
        """Fetch social posts immediately, then repeat every SOCIAL_INTERVAL_S seconds."""
        while self._running:
            try:
                await run_social_aggregation(redis)
            except Exception as exc:
                log.error("social_aggregation_error", error=str(exc))
            if not self._running:
                break
            await asyncio.sleep(SOCIAL_INTERVAL_S)


# Singleton — imported by the FastAPI lifespan
scheduler = WorldMonitorScheduler()
