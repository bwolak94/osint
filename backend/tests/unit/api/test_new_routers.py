"""Unit tests for the 5 new backend routers added in batch 2.

Tests cover: happy-path responses, authentication failures, and key edge cases.
External DB calls are mocked via AsyncMock so tests run without a live database.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

FAKE_USER_ID = uuid.uuid4()
FAKE_INV_ID = uuid.uuid4()


def _make_user():
    user = MagicMock()
    user.id = FAKE_USER_ID
    user.email = "test@example.com"
    user.role = "user"
    return user


def _make_inv(owner_id=None):
    inv = MagicMock()
    inv.id = FAKE_INV_ID
    inv.owner_id = owner_id or FAKE_USER_ID
    inv.title = "Test investigation"
    inv.description = "desc"
    inv.seed_inputs = []
    inv.created_at = None
    inv.updated_at = None
    return inv


# ---------------------------------------------------------------------------
# investigation_risk_score
# ---------------------------------------------------------------------------

class TestInvestigationRiskScore:

    @pytest.fixture
    def app(self):
        from src.api.v1.investigation_risk_score import router
        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        return app

    async def test_returns_risk_score(self, app):
        user = _make_user()
        inv = _make_inv()

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = inv
        mock_result.scalars.return_value = mock_scalars

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        with (
            patch("src.api.v1.investigation_risk_score.get_current_user", return_value=user),
            patch("src.api.v1.investigation_risk_score.async_session_factory", return_value=mock_db),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/api/v1/investigations/{FAKE_INV_ID}/risk-score")
        assert resp.status_code == 200
        data = resp.json()
        assert "score" in data
        assert "label" in data

    async def test_404_when_not_found(self, app):
        user = _make_user()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        with (
            patch("src.api.v1.investigation_risk_score.get_current_user", return_value=user),
            patch("src.api.v1.investigation_risk_score.async_session_factory", return_value=mock_db),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/api/v1/investigations/{FAKE_INV_ID}/risk-score")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# stix_export
# ---------------------------------------------------------------------------

class TestStixExport:

    @pytest.fixture
    def app(self):
        from src.api.v1.stix_export import router
        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        return app

    async def test_returns_stix_bundle(self, app):
        user = _make_user()
        inv = _make_inv(owner_id=FAKE_USER_ID)
        inv.created_at = None
        inv.updated_at = None

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = inv
        mock_result.scalars.return_value = mock_scalars

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        with (
            patch("src.api.v1.stix_export.get_current_user", return_value=user),
            patch("src.api.v1.stix_export.async_session_factory", return_value=mock_db),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/api/v1/investigations/{FAKE_INV_ID}/export/stix")
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "bundle"
        assert "objects" in data

    async def test_403_non_owner_without_acl(self, app):
        user = _make_user()
        inv = _make_inv(owner_id=uuid.uuid4())  # different owner

        mock_result_inv = MagicMock()
        mock_result_inv.scalar_one_or_none.return_value = inv

        mock_result_acl = MagicMock()
        mock_result_acl.scalar_one_or_none.return_value = None  # no ACL entry

        call_count = 0

        async def fake_execute(_stmt):
            nonlocal call_count
            call_count += 1
            return mock_result_inv if call_count == 1 else mock_result_acl

        mock_db = AsyncMock()
        mock_db.execute = fake_execute

        with (
            patch("src.api.v1.stix_export.get_current_user", return_value=user),
            patch("src.api.v1.stix_export.async_session_factory", return_value=mock_db),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/api/v1/investigations/{FAKE_INV_ID}/export/stix")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# investigation_acl
# ---------------------------------------------------------------------------

class TestInvestigationACL:

    @pytest.fixture
    def app(self):
        from src.api.v1.investigation_acl import router
        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        return app

    async def test_list_acl_owner(self, app):
        user = _make_user()
        inv = _make_inv(owner_id=FAKE_USER_ID)

        mock_acl_rows = MagicMock()
        mock_acl_rows.scalars.return_value.all.return_value = []

        call_count = 0
        async def fake_execute(_stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                r = MagicMock(); r.scalar_one_or_none.return_value = inv; return r
            r2 = MagicMock(); r2.scalar_one_or_none.return_value = None; return r2

        mock_db = AsyncMock()
        mock_db.execute = fake_execute
        mock_db.scalars = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[])))

        with (
            patch("src.api.v1.investigation_acl.get_current_user", return_value=user),
            patch("src.api.v1.investigation_acl.async_session_factory", return_value=mock_db),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/api/v1/investigations/{FAKE_INV_ID}/acl")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# scanner_quota
# ---------------------------------------------------------------------------

class TestScannerQuota:

    @pytest.fixture
    def app(self):
        from src.api.v1.scanner_quota import router
        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        return app

    async def test_list_quotas_empty(self, app):
        user = _make_user()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        with (
            patch("src.api.v1.scanner_quota.get_current_user", return_value=user),
            patch("src.api.v1.scanner_quota.async_session_factory", return_value=mock_db),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/api/v1/scanner-quota")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_set_quota_rejects_foreign_workspace(self, app):
        user = _make_user()
        other_workspace = str(uuid.uuid4())
        mock_db = AsyncMock()

        with (
            patch("src.api.v1.scanner_quota.get_current_user", return_value=user),
            patch("src.api.v1.scanner_quota.async_session_factory", return_value=mock_db),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/api/v1/scanner-quota",
                    json={
                        "scanner_name": "shodan",
                        "requests_limit": 100,
                        "workspace_id": other_workspace,
                    },
                )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# pivot_recommendations
# ---------------------------------------------------------------------------

class TestPivotRecommendations:

    @pytest.fixture
    def app(self):
        from src.api.v1.pivot_recommendations import router
        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        return app

    async def test_returns_recommendations(self, app):
        user = _make_user()
        inv = _make_inv()

        mock_scalars_empty = MagicMock()
        mock_scalars_empty.all.return_value = []

        call_count = 0
        async def fake_execute(_stmt):
            nonlocal call_count
            call_count += 1
            r = MagicMock()
            if call_count == 1:
                r.scalar_one_or_none.return_value = inv
            else:
                r.scalars.return_value = mock_scalars_empty
            return r

        mock_db = AsyncMock()
        mock_db.execute = fake_execute

        fake_llm_result = {
            "recommendations": [
                {"scanner": "shodan", "reason": "open ports", "target": "1.2.3.4", "confidence": "high"}
            ],
            "summary": "Investigate the IP address for open services.",
        }

        with (
            patch("src.api.v1.pivot_recommendations.get_current_user", return_value=user),
            patch("src.api.v1.pivot_recommendations.async_session_factory", return_value=mock_db),
            patch("src.api.v1.pivot_recommendations._call_llm", new=AsyncMock(return_value=fake_llm_result)),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/api/v1/investigations/{FAKE_INV_ID}/pivot-recommendations")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["recommendations"]) == 1
        assert data["recommendations"][0]["scanner"] == "shodan"

    async def test_404_when_inv_not_found(self, app):
        user = _make_user()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        with (
            patch("src.api.v1.pivot_recommendations.get_current_user", return_value=user),
            patch("src.api.v1.pivot_recommendations.async_session_factory", return_value=mock_db),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(f"/api/v1/investigations/{FAKE_INV_ID}/pivot-recommendations")
        assert resp.status_code == 404
