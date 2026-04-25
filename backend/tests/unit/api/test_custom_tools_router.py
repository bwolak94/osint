"""Integration tests for custom tools router. (#37)"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from src.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_list_tools_requires_auth():
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.get("/api/v1/tools/custom")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_create_tool_requires_auth():
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/tools/custom",
            json={"name": "test-tool", "docker_image": "alpine:latest"},
        )
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_delete_tool_requires_auth():
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.delete("/api/v1/tools/custom/nonexistent-id")
    assert resp.status_code == 401
