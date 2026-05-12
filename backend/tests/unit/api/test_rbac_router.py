"""Integration tests for RBAC router. (#37)"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from src.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_list_roles_requires_auth():
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.get("/api/v1/rbac/roles")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_list_users_requires_auth():
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.get("/api/v1/rbac/users")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_audit_log_requires_auth():
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.get("/api/v1/rbac/audit-log")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_assign_role_requires_auth():
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.put(
            "/api/v1/rbac/users/00000000-0000-0000-0000-000000000000/role",
            json={"role": "viewer"},
        )
    assert resp.status_code == 401
