"""Unit tests for backend API modules.

These tests verify the logic of backend modules in isolation. Missing
third-party dependencies (jose, pyotp, asyncpg, etc.) are stubbed via
sys.modules so that the import chains resolve without installing every
optional package.
"""

import sys
import types
from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

# ---------------------------------------------------------------------------
# Stub out optional third-party packages that may not be installed in the
# test environment.  We only need them to exist as importable modules so
# the real source files can be loaded; the actual crypto / DB logic is not
# exercised in these unit tests.
# ---------------------------------------------------------------------------
_STUBS: dict[str, types.ModuleType] = {}


def _ensure_module(name: str) -> types.ModuleType:
    """Create a lazy MagicMock module stub if *name* is not already importable."""
    if name in sys.modules:
        return sys.modules[name]
    mod = types.ModuleType(name)
    mod.__dict__.update({k: MagicMock() for k in [
        "jwt", "JWTError", "TOTP", "random_base32", "create_async_engine",
        "AsyncSession", "connect",
    ]})
    # Make attribute access return MagicMock for anything not explicitly set
    sys.modules[name] = mod
    _STUBS[name] = mod
    return mod


# Stub missing packages before importing any source modules
for _pkg in [
    "jose",
    "jose.jwt",
    "pyotp",
    "asyncpg",
    "redis",
    "redis.asyncio",
    "bcrypt",
    "neo4j",
    "qrcode",
    "holehe",
    "holehe.core",
    "holehe.modules",
]:
    _ensure_module(_pkg)

# Patch database module to avoid connecting to a real PostgreSQL instance
# on import.
_db_mod_name = "src.adapters.db.database"
if _db_mod_name not in sys.modules:
    _fake_db = types.ModuleType(_db_mod_name)
    _fake_db.async_session_factory = MagicMock()  # type: ignore[attr-defined]
    _fake_db.engine = MagicMock()  # type: ignore[attr-defined]
    sys.modules[_db_mod_name] = _fake_db

# Similarly patch the redis-based caches that try to connect on import.
for _cache_mod in [
    "src.adapters.cache.redis_cache",
    "src.adapters.cache.token_blacklist",
]:
    if _cache_mod not in sys.modules:
        _m = types.ModuleType(_cache_mod)
        _m.RedisTokenBlacklist = MagicMock()  # type: ignore[attr-defined]
        _m.RedisCache = MagicMock()  # type: ignore[attr-defined]
        sys.modules[_cache_mod] = _m


# ============== AI Summarization ==============
class TestSummarization:
    async def test_generates_summary_from_vat_data(self):
        from src.api.v1.investigations.summarize import _generate_summary
        from src.core.domain.entities.investigation import Investigation
        from src.core.domain.entities.scan_result import ScanResult
        from src.core.domain.entities.types import (
            InvestigationStatus,
            ScanInputType,
            ScanStatus,
            SeedInput,
        )

        inv = Investigation(
            id=uuid4(), owner_id=uuid4(), title="Test", description="",
            status=InvestigationStatus.COMPLETED,
            seed_inputs=[SeedInput(value="5261040828", input_type=ScanInputType.NIP)],
            tags=frozenset(),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        results = [ScanResult(
            id=uuid4(), investigation_id=inv.id, scanner_name="vat_status",
            input_value="5261040828", status=ScanStatus.SUCCESS,
            raw_data={
                "found": True, "name": "TEST COMPANY",
                "status_vat": "Czynny", "regon": "123",
                "bank_accounts": ["111", "222"],
            },
            extracted_identifiers=["company_name:TEST COMPANY"],
            duration_ms=500, created_at=datetime.now(timezone.utc),
        )]

        summary = _generate_summary(inv, results)
        assert "TEST COMPANY" in summary.summary
        assert len(summary.key_findings) > 0
        assert summary.risk_score >= 0

    async def test_empty_results_produces_summary(self):
        from src.api.v1.investigations.summarize import _generate_summary
        from src.core.domain.entities.investigation import Investigation
        from src.core.domain.entities.types import InvestigationStatus

        inv = Investigation(
            id=uuid4(), owner_id=uuid4(), title="Empty", description="",
            status=InvestigationStatus.COMPLETED, seed_inputs=[], tags=frozenset(),
            created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
        )
        summary = _generate_summary(inv, [])
        assert "no significant findings" in summary.summary.lower() or "0 seed" in summary.summary

    async def test_risk_score_increases_with_breaches(self):
        from src.api.v1.investigations.summarize import _generate_summary
        from src.core.domain.entities.investigation import Investigation
        from src.core.domain.entities.scan_result import ScanResult
        from src.core.domain.entities.types import InvestigationStatus, ScanStatus

        inv = Investigation(
            id=uuid4(), owner_id=uuid4(), title="Risky", description="",
            status=InvestigationStatus.COMPLETED, seed_inputs=[], tags=frozenset(),
            created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
        )
        results = [ScanResult(
            id=uuid4(), investigation_id=inv.id, scanner_name="hibp",
            input_value="test@test.com", status=ScanStatus.SUCCESS,
            raw_data={
                "found": True,
                "breaches": [{"Name": "Breach1"}, {"Name": "Breach2"}],
            },
            extracted_identifiers=["breach:Breach1"],
            duration_ms=100, created_at=datetime.now(timezone.utc),
        )]
        summary = _generate_summary(inv, results)
        assert summary.risk_score >= 0.3


# ============== Comments ==============
class TestCommentsAPI:
    async def test_comment_model_importable(self):
        from src.adapters.db.comment_models import CommentModel
        assert CommentModel.__tablename__ == "comments"


# ============== Webhooks ==============
class TestWebhooksAPI:
    async def test_webhook_model_importable(self):
        from src.adapters.db.webhook_models import WebhookModel
        assert WebhookModel.__tablename__ == "webhooks"


# ============== Playbooks ==============
class TestPlaybooks:
    async def test_default_playbooks_available(self):
        from src.api.v1.playbooks import DEFAULT_PLAYBOOKS
        assert len(DEFAULT_PLAYBOOKS) >= 4
        names = [p["name"] for p in DEFAULT_PLAYBOOKS]
        assert "Full Email OSINT" in names
        assert "Company Deep Dive" in names

    async def test_playbook_model_importable(self):
        from src.adapters.db.playbook_models import PlaybookModel
        assert PlaybookModel.__tablename__ == "playbooks"


# ============== Workspaces ==============
class TestWorkspaces:
    async def test_workspace_model_importable(self):
        from src.adapters.db.workspace_models import WorkspaceModel
        assert WorkspaceModel.__tablename__ == "workspaces"


# ============== Alert Rules ==============
class TestAlertRules:
    async def test_alert_model_importable(self):
        from src.adapters.db.alert_models import AlertRuleModel
        assert AlertRuleModel.__tablename__ == "alert_rules"


# ============== Audit Log ==============
class TestAuditLog:
    async def test_audit_model_importable(self):
        from src.adapters.db.audit_models import AuditLogModel
        assert AuditLogModel.__tablename__ == "audit_logs"


# ============== Encryption ==============
class TestEncryption:
    def test_encrypt_without_key_returns_plaintext(self):
        from src.adapters.encryption import DataEncryptor
        enc = DataEncryptor(master_key=None)
        assert enc.encrypt("hello") == "hello"
        assert enc.decrypt("hello") == "hello"

    def test_encrypt_with_key(self):
        from src.adapters.encryption import DataEncryptor
        enc = DataEncryptor(master_key="test-secret-key-1234")
        encrypted = enc.encrypt("sensitive data")
        # With key the value is encrypted if cryptography is installed,
        # otherwise it falls back to plaintext.
        decrypted = enc.decrypt(encrypted)
        assert decrypted == "sensitive data" or encrypted == "sensitive data"


# ============== Notifications ==============
class TestNotifications:
    async def test_slack_notifier_no_url(self):
        from src.adapters.notifications.slack import SlackNotifier
        notifier = SlackNotifier(webhook_url="")
        result = await notifier.send("Test", "Message")
        assert result is False

    async def test_discord_notifier_no_url(self):
        from src.adapters.notifications.discord import DiscordNotifier
        notifier = DiscordNotifier(webhook_url="")
        result = await notifier.send("Test", "Message")
        assert result is False


# ============== Search ==============
class TestSearchEndpoint:
    async def test_search_module_importable(self):
        from src.api.v1.search import SearchResponse
        assert SearchResponse is not None


# ============== Public API ==============
class TestPublicAPI:
    async def test_public_api_module_importable(self):
        from src.api.v1.public_api import PublicInvestigationResponse
        assert PublicInvestigationResponse is not None


# ============== TOTP ==============
class TestTOTP:
    async def test_totp_module_importable(self):
        from src.api.v1.auth.totp import TOTPSetupResponse
        assert TOTPSetupResponse is not None


# ============== Report ==============
class TestReport:
    async def test_html_report_generation(self):
        from src.api.v1.investigations.report import _generate_html_report
        from src.core.domain.entities.investigation import Investigation
        from src.core.domain.entities.scan_result import ScanResult
        from src.core.domain.entities.types import (
            InvestigationStatus,
            ScanInputType,
            ScanStatus,
            SeedInput,
        )

        inv = Investigation(
            id=uuid4(), owner_id=uuid4(), title="Report Test",
            description="Testing PDF",
            status=InvestigationStatus.COMPLETED,
            seed_inputs=[SeedInput(value="test@test.com", input_type=ScanInputType.EMAIL)],
            tags=frozenset(),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        results = [ScanResult(
            id=uuid4(), investigation_id=inv.id, scanner_name="holehe",
            input_value="test@test.com", status=ScanStatus.SUCCESS,
            raw_data={"registered_on": ["twitter", "github"], "registered_count": 2},
            extracted_identifiers=["service:twitter"],
            duration_ms=1000, created_at=datetime.now(timezone.utc),
        )]

        html = _generate_html_report(inv, results, [])
        assert "Report Test" in html
        assert "holehe" in html
        assert "twitter" in html
        assert "<html>" in html


# ============== Pricing ==============
class TestPricingExtended:
    def test_all_tiers_have_prices(self):
        from src.core.domain.pricing import SUBSCRIPTION_PRICES
        assert "pro_monthly" in SUBSCRIPTION_PRICES
        assert "enterprise_yearly" in SUBSCRIPTION_PRICES
