"""Shared pytest fixtures."""

import asyncio
from typing import AsyncGenerator, Generator

import pytest


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create a session-scoped event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def redis_client() -> AsyncGenerator:
    """Provide a Redis client and flush the test database after each test.

    Flushes only db=15 (a dedicated test database) so unit tests that exercise
    circuit breakers or cache logic never pollute production data and always
    start with clean state. (#32)
    """
    import redis.asyncio as aioredis

    client = aioredis.from_url("redis://localhost:6379/15", decode_responses=True)
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()
