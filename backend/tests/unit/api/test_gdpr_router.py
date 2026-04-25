"""Integration tests for GDPR router. (#37)"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from src.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_data_export_requires_auth():
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.post("/api/v1/gdpr/data-export")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_erasure_request_requires_auth():
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.post("/api/v1/gdpr/erasure-request", json={"reason": "test"})
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_retention_policy_requires_auth():
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.get("/api/v1/gdpr/retention-policy")
    assert resp.status_code == 401
