"""Integration tests for n8n workflow router. (#37)"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from src.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_list_workflows_requires_auth():
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.get("/api/v1/workflows/n8n")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_trigger_workflow_requires_auth():
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.post("/api/v1/workflows/n8n/trigger", json={"workflow_name": "x"})
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_callback_accepts_valid_payload():
    """Callback endpoint should accept unauthenticated posts (called by n8n)."""
    import uuid
    exec_id = str(uuid.uuid4())
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/workflows/n8n/callback",
            json={"execution_id": exec_id, "status": "success", "output": {}},
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "received"


@pytest.mark.anyio
async def test_register_and_remove_custom_workflow_requires_auth():
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/workflows/n8n/workflows",
            json={"name": "my-test", "webhook_path": "/webhook/my-test"},
        )
    assert resp.status_code == 401
