from uuid import UUID
from datetime import datetime
from src.core.domain.events import (
    DomainEvent, InvestigationCreated, ScanCompleted,
    IdentityResolved, GraphEdgeCreated, PaymentReceived,
)
from uuid import uuid4


class TestDomainEvents:
    def test_event_has_unique_id(self):
        e1 = DomainEvent()
        e2 = DomainEvent()
        assert e1.event_id != e2.event_id

    def test_event_has_timestamp(self):
        event = DomainEvent()
        assert isinstance(event.occurred_at, datetime)

    def test_event_has_correlation_id(self):
        event = DomainEvent()
        assert isinstance(event.correlation_id, UUID)

    def test_event_is_frozen(self):
        import pytest
        event = DomainEvent()
        with pytest.raises(AttributeError):
            event.event_id = uuid4()

    def test_investigation_created_fields(self):
        inv_id = uuid4()
        owner_id = uuid4()
        event = InvestigationCreated(
            investigation_id=inv_id,
            owner_id=owner_id,
            seed_inputs=(),
        )
        assert event.investigation_id == inv_id
        assert event.owner_id == owner_id

    def test_scan_completed_fields(self):
        event = ScanCompleted(
            scan_result_id=uuid4(),
            investigation_id=uuid4(),
            scanner_name="holehe",
            identifiers_found=("user@test.com", "username123"),
        )
        assert event.scanner_name == "holehe"
        assert len(event.identifiers_found) == 2

    def test_identity_resolved_fields(self):
        event = IdentityResolved(
            identity_id=uuid4(),
            investigation_id=uuid4(),
            merged_from=(uuid4(), uuid4()),
            confidence_score=0.85,
        )
        assert event.confidence_score == 0.85
        assert len(event.merged_from) == 2

    def test_payment_received_fields(self):
        event = PaymentReceived(
            payment_id=uuid4(),
            user_id=uuid4(),
            amount_crypto="0.005",
            currency="BTC",
            subscription_tier="pro",
        )
        assert event.currency == "BTC"
        assert event.amount_crypto == "0.005"
