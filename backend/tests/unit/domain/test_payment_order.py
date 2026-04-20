"""Tests for PaymentOrder domain entity."""

import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from uuid import uuid4

from src.core.domain.entities.payment import (
    PaymentOrder, PaymentOrderStatus, BillingPeriod,
)


def make_order(**overrides) -> PaymentOrder:
    defaults = {
        "id": uuid4(),
        "user_id": uuid4(),
        "subscription_tier": "pro",
        "billing_period": BillingPeriod.MONTHLY,
        "amount_usd": Decimal("29.99"),
    }
    defaults.update(overrides)
    return PaymentOrder(**defaults)


class TestPaymentOrder:
    def test_default_status_is_pending(self):
        order = make_order()
        assert order.status == PaymentOrderStatus.PENDING

    def test_mark_finished(self):
        order = make_order()
        finished = order.mark_finished(
            amount_crypto=Decimal("0.000412"),
            currency="BTC",
        )
        assert finished.status == PaymentOrderStatus.FINISHED
        assert finished.amount_crypto == Decimal("0.000412")
        assert finished.crypto_currency == "BTC"
        assert order.status == PaymentOrderStatus.PENDING  # original unchanged

    def test_activate_subscription(self):
        order = make_order()
        finished = order.mark_finished(Decimal("0.001"), "ETH")
        expires = datetime.now(timezone.utc) + timedelta(days=31)
        activated = finished.activate_subscription(expires)
        assert activated.subscription_activated_at is not None
        assert activated.subscription_expires_at == expires

    def test_mark_failed(self):
        order = make_order()
        failed = order.mark_failed()
        assert failed.status == PaymentOrderStatus.FAILED

    def test_mark_expired(self):
        order = make_order()
        expired = order.mark_expired()
        assert expired.status == PaymentOrderStatus.EXPIRED

    def test_is_completed_only_when_finished(self):
        order = make_order()
        assert order.is_completed is False
        finished = order.mark_finished(Decimal("0.001"), "BTC")
        assert finished.is_completed is True

    def test_billing_period_values(self):
        assert BillingPeriod.MONTHLY.value == "monthly"
        assert BillingPeriod.YEARLY.value == "yearly"
