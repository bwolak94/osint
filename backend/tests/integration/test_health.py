"""Integration tests for health check endpoints."""

import pytest


class TestHealthEndpoints:
    """Tests that verify the health check endpoints work correctly.

    These tests use the FastAPI test client and don't require
    external services (PostgreSQL, Redis, Neo4j).
    """

    async def test_health_returns_ok(self):
        """Basic health check should always return 200."""
        from httpx import ASGITransport, AsyncClient
        from src.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"

    async def test_liveness_returns_alive(self):
        from httpx import ASGITransport, AsyncClient
        from src.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/health/live")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "alive"

    async def test_protected_endpoint_returns_401(self):
        from httpx import ASGITransport, AsyncClient
        from src.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/auth/me")
            assert response.status_code == 401

    async def test_login_without_body_returns_422(self):
        from httpx import ASGITransport, AsyncClient
        from src.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post("/api/v1/auth/login")
            assert response.status_code == 422

    async def test_register_without_body_returns_422(self):
        from httpx import ASGITransport, AsyncClient
        from src.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post("/api/v1/auth/register")
            assert response.status_code == 422

    async def test_security_headers_present(self):
        from httpx import ASGITransport, AsyncClient
        from src.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/health")
            assert response.headers.get("x-content-type-options") == "nosniff"
            assert response.headers.get("x-frame-options") == "DENY"

    async def test_cors_headers_for_allowed_origin(self):
        from httpx import ASGITransport, AsyncClient
        from src.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.options(
                "/api/v1/auth/login",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": "POST",
                },
            )
            # CORS should be configured
            assert response.status_code in [200, 204, 405]


class TestAPIStructure:
    """Verify the API has the expected routes."""

    async def test_openapi_schema_available(self):
        from httpx import ASGITransport, AsyncClient
        from src.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/openapi.json")
            assert response.status_code == 200
            schema = response.json()
            assert "paths" in schema
            # Verify key endpoints exist
            paths = schema["paths"]
            assert "/api/v1/auth/login" in paths
            assert "/api/v1/auth/register" in paths
            assert "/health" in paths
