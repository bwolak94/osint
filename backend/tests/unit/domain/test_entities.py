import pytest
from datetime import datetime, timezone
from uuid import uuid4

from src.core.domain.entities import (
    User, Investigation, Identity, ScanResult,
    UserRole, SubscriptionTier, Feature, InvestigationStatus,
    ScanInputType, ScanStatus, SeedInput,
)
from src.core.domain.value_objects import Email, ConfidenceScore


def make_user(**overrides) -> User:
    defaults = {
        "id": uuid4(),
        "email": Email("analyst@example.com"),
        "hashed_password": "hashed",
        "role": UserRole.ANALYST,
        "subscription_tier": SubscriptionTier.PRO,
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    return User(**defaults)


def make_investigation(**overrides) -> Investigation:
    defaults = {
        "id": uuid4(),
        "owner_id": uuid4(),
        "title": "Test Investigation",
        "description": "Testing",
        "status": InvestigationStatus.DRAFT,
        "seed_inputs": [],
        "tags": frozenset(),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    return Investigation(**defaults)


def make_identity(**overrides) -> Identity:
    defaults = {
        "id": uuid4(),
        "investigation_id": uuid4(),
        "display_name": "John Doe",
        "emails": frozenset({Email("john@example.com")}),
        "phones": frozenset(),
        "usernames": frozenset({"johndoe"}),
        "urls": frozenset(),
        "nip": None,
        "confidence_score": ConfidenceScore(0.7),
        "sources": frozenset({"holehe"}),
        "metadata": {},
        "created_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    return Identity(**defaults)


class TestUser:
    def test_analyst_can_create_investigation(self):
        user = make_user(role=UserRole.ANALYST)
        assert user.can_create_investigation() is True

    def test_admin_can_create_investigation(self):
        user = make_user(role=UserRole.ADMIN)
        assert user.can_create_investigation() is True

    def test_viewer_cannot_create_investigation(self):
        user = make_user(role=UserRole.VIEWER)
        assert user.can_create_investigation() is False

    def test_inactive_user_cannot_create_investigation(self):
        user = make_user(is_active=False)
        assert user.can_create_investigation() is False

    def test_pro_can_use_deep_scan(self):
        user = make_user(subscription_tier=SubscriptionTier.PRO)
        assert user.can_use_feature(Feature.DEEP_SCAN) is True

    def test_free_cannot_use_deep_scan(self):
        user = make_user(subscription_tier=SubscriptionTier.FREE)
        assert user.can_use_feature(Feature.DEEP_SCAN) is False

    def test_enterprise_can_use_all_features(self):
        user = make_user(subscription_tier=SubscriptionTier.ENTERPRISE)
        for feature in Feature:
            assert user.can_use_feature(feature) is True

    def test_upgrade_returns_new_instance(self):
        user = make_user(subscription_tier=SubscriptionTier.FREE)
        upgraded = user.upgrade_subscription(SubscriptionTier.PRO)
        assert upgraded.subscription_tier == SubscriptionTier.PRO
        assert user.subscription_tier == SubscriptionTier.FREE  # original unchanged
        assert upgraded.id == user.id  # same user


class TestInvestigation:
    def test_add_seed_in_draft(self):
        inv = make_investigation(status=InvestigationStatus.DRAFT)
        seed = SeedInput(value="test@example.com", input_type=ScanInputType.EMAIL)
        updated = inv.add_seed(seed)
        assert seed in updated.seed_inputs
        assert seed not in inv.seed_inputs  # original unchanged

    def test_cannot_add_seed_when_running(self):
        inv = make_investigation(status=InvestigationStatus.RUNNING)
        seed = SeedInput(value="test@example.com", input_type=ScanInputType.EMAIL)
        with pytest.raises(ValueError):
            inv.add_seed(seed)

    def test_mark_running_from_draft(self):
        inv = make_investigation(status=InvestigationStatus.DRAFT)
        running = inv.mark_running()
        assert running.status == InvestigationStatus.RUNNING

    def test_mark_running_from_paused(self):
        inv = make_investigation(status=InvestigationStatus.PAUSED)
        running = inv.mark_running()
        assert running.status == InvestigationStatus.RUNNING

    def test_cannot_mark_running_from_completed(self):
        inv = make_investigation(status=InvestigationStatus.COMPLETED)
        with pytest.raises(ValueError):
            inv.mark_running()

    def test_complete_sets_completed_at(self):
        inv = make_investigation(status=InvestigationStatus.RUNNING)
        completed = inv.complete()
        assert completed.status == InvestigationStatus.COMPLETED
        assert completed.completed_at is not None

    def test_pause_running_investigation(self):
        inv = make_investigation(status=InvestigationStatus.RUNNING)
        paused = inv.pause()
        assert paused.status == InvestigationStatus.PAUSED

    def test_cannot_pause_draft(self):
        inv = make_investigation(status=InvestigationStatus.DRAFT)
        with pytest.raises(ValueError):
            inv.pause()

    def test_archive_completed(self):
        inv = make_investigation(status=InvestigationStatus.COMPLETED)
        archived = inv.archive()
        assert archived.status == InvestigationStatus.ARCHIVED

    def test_cannot_archive_running(self):
        inv = make_investigation(status=InvestigationStatus.RUNNING)
        with pytest.raises(ValueError):
            inv.archive()

    def test_owner_can_delete_draft(self):
        owner_id = uuid4()
        inv = make_investigation(owner_id=owner_id, status=InvestigationStatus.DRAFT)
        user = make_user(id=owner_id)
        assert inv.can_be_deleted_by(user) is True

    def test_non_owner_non_admin_cannot_delete(self):
        inv = make_investigation(status=InvestigationStatus.DRAFT)
        user = make_user(role=UserRole.ANALYST)
        assert inv.can_be_deleted_by(user) is False

    def test_admin_can_delete_draft(self):
        inv = make_investigation(status=InvestigationStatus.DRAFT)
        admin = make_user(role=UserRole.ADMIN)
        assert inv.can_be_deleted_by(admin) is True

    def test_cannot_delete_running(self):
        owner_id = uuid4()
        inv = make_investigation(owner_id=owner_id, status=InvestigationStatus.RUNNING)
        user = make_user(id=owner_id)
        assert inv.can_be_deleted_by(user) is False


class TestIdentity:
    def test_merge_combines_emails(self):
        id1 = make_identity(emails=frozenset({Email("a@b.com")}))
        id2 = make_identity(emails=frozenset({Email("c@d.com")}))
        merged = id1.merge_with(id2)
        assert Email("a@b.com") in merged.emails
        assert Email("c@d.com") in merged.emails

    def test_merge_takes_higher_confidence(self):
        id1 = make_identity(confidence_score=ConfidenceScore(0.5))
        id2 = make_identity(confidence_score=ConfidenceScore(0.9))
        merged = id1.merge_with(id2)
        assert merged.confidence_score.value == 0.9

    def test_merge_combines_sources(self):
        id1 = make_identity(sources=frozenset({"holehe"}))
        id2 = make_identity(sources=frozenset({"maigret"}))
        merged = id1.merge_with(id2)
        assert "holehe" in merged.sources
        assert "maigret" in merged.sources

    def test_add_email_returns_new_instance(self):
        identity = make_identity(emails=frozenset({Email("a@b.com")}))
        updated = identity.add_email(Email("new@example.com"), "manual")
        assert Email("new@example.com") in updated.emails
        assert Email("new@example.com") not in identity.emails  # immutability

    def test_add_email_adds_source(self):
        identity = make_identity(sources=frozenset({"holehe"}))
        updated = identity.add_email(Email("new@example.com"), "maigret")
        assert "maigret" in updated.sources

    def test_update_confidence(self):
        identity = make_identity(confidence_score=ConfidenceScore(0.5))
        updated = identity.update_confidence(ConfidenceScore(0.9))
        assert updated.confidence_score.value == 0.9
        assert identity.confidence_score.value == 0.5

    def test_is_same_as_shared_email(self):
        shared_email = Email("shared@example.com")
        id1 = make_identity(emails=frozenset({shared_email}))
        id2 = make_identity(emails=frozenset({shared_email, Email("other@example.com")}))
        assert id1.is_same_as(id2) is True

    def test_is_same_as_no_overlap(self):
        id1 = make_identity(
            display_name="Alice",
            emails=frozenset({Email("alice@a.com")}),
            usernames=frozenset({"alice1"}),
        )
        id2 = make_identity(
            display_name="Bob",
            emails=frozenset({Email("bob@b.com")}),
            usernames=frozenset({"bob1"}),
        )
        assert id1.is_same_as(id2) is False

    def test_is_same_as_same_name_and_username(self):
        id1 = make_identity(
            display_name="John Doe",
            emails=frozenset({Email("john1@a.com")}),
            usernames=frozenset({"johndoe"}),
        )
        id2 = make_identity(
            display_name="John Doe",
            emails=frozenset({Email("john2@b.com")}),
            usernames=frozenset({"johndoe", "jdoe"}),
        )
        assert id1.is_same_as(id2) is True


class TestScanResult:
    def test_is_successful(self):
        result = ScanResult(
            id=uuid4(),
            investigation_id=uuid4(),
            scanner_name="holehe",
            input_value="test@example.com",
            status=ScanStatus.SUCCESS,
            raw_data={"found": True},
            extracted_identifiers=["username1"],
            duration_ms=150,
            created_at=datetime.now(timezone.utc),
        )
        assert result.is_successful() is True

    def test_failed_not_successful(self):
        result = ScanResult(
            id=uuid4(),
            investigation_id=uuid4(),
            scanner_name="holehe",
            input_value="test@example.com",
            status=ScanStatus.FAILED,
            raw_data={},
            extracted_identifiers=[],
            duration_ms=50,
            created_at=datetime.now(timezone.utc),
            error_message="Connection timeout",
        )
        assert result.is_successful() is False

    def test_has_findings(self):
        result = ScanResult(
            id=uuid4(),
            investigation_id=uuid4(),
            scanner_name="maigret",
            input_value="johndoe",
            status=ScanStatus.SUCCESS,
            raw_data={},
            extracted_identifiers=["john@example.com", "johndoe123"],
            duration_ms=200,
            created_at=datetime.now(timezone.utc),
        )
        assert result.has_findings() is True

    def test_no_findings(self):
        result = ScanResult(
            id=uuid4(),
            investigation_id=uuid4(),
            scanner_name="holehe",
            input_value="nobody@example.com",
            status=ScanStatus.SUCCESS,
            raw_data={},
            extracted_identifiers=[],
            duration_ms=100,
            created_at=datetime.now(timezone.utc),
        )
        assert result.has_findings() is False
