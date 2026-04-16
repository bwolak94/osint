"""End-to-end test for the payment webhook -> subscription upgrade flow."""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from src.core.domain.entities.payment import BillingPeriod, PaymentOrder, PaymentOrderStatus
from src.core.domain.entities.user import User
from src.core.domain.entities.types import UserRole, SubscriptionTier
from src.core.domain.value_objects.email import Email
from src.core.use_cases.payments.create_payment import CreatePaymentCommand, CreatePaymentUseCase
from src.core.use_cases.payments.process_webhook import ProcessWebhookUseCase, WebhookPayload


class FakePaymentRepo:
    def __init__(self):
        self._orders = {}
        self._by_ext = {}

    async def save(self, order):
        self._orders[order.id] = order
        if order.external_payment_id:
            self._by_ext[order.external_payment_id] = order
        return order

    async def get_by_id(self, oid):
        return self._orders.get(oid)

    async def get_by_external_id(self, eid):
        return self._by_ext.get(eid)

    async def get_by_user(self, uid):
        return [o for o in self._orders.values() if o.user_id == uid]

    async def is_processed(self, eid):
        o = self._by_ext.get(eid)
        return o is not None and o.status == PaymentOrderStatus.FINISHED


class FakeWebhookLogRepo:
    def __init__(self):
        self.logs = []
    async def save(self, log):
        self.logs.append(log)
        return log


class FakeUserRepo:
    def __init__(self):
        self._users = {}
    async def get_by_id(self, uid):
        return self._users.get(uid)
    async def get_by_email(self, e):
        return None
    async def save(self, u):
        self._users[u.id] = u
        return u
    async def delete(self, uid):
        pass
    def add(self, u):
        self._users[u.id] = u


class FakeGateway:
    async def create_invoice(self, **kw):
        from src.core.ports.payment_gateway import PaymentData
        return PaymentData(
            payment_id="ext_100", payment_url="https://pay.example.com/ext_100",
            pay_amount=Decimal("0.001"), pay_currency=kw.get("pay_currency", "BTC"),
            price_amount=kw.get("price_amount", Decimal("29.99")), price_currency="USD",
        )


class FakeEventPublisher:
    def __init__(self):
        self.events = []
    async def publish(self, e):
        self.events.append(e)
    async def publish_many(self, es):
        self.events.extend(es)


class TestPaymentWebhookFullFlow:
    """Tests the complete flow: create payment -> webhook -> subscription upgrade."""

    async def test_full_payment_flow(self):
        # Setup
        user = User(
            id=uuid4(), email=Email("buyer@test.com"), hashed_password="h",
            role=UserRole.ANALYST, subscription_tier=SubscriptionTier.FREE,
            is_active=True, created_at=datetime.now(timezone.utc),
        )
        user_repo = FakeUserRepo()
        user_repo.add(user)
        payment_repo = FakePaymentRepo()
        webhook_log_repo = FakeWebhookLogRepo()
        gateway = FakeGateway()
        events = FakeEventPublisher()

        # Step 1: Create payment
        create_uc = CreatePaymentUseCase(
            payment_repo=payment_repo, gateway=gateway,
            base_url="http://test", frontend_url="http://test",
        )
        result = await create_uc.execute(CreatePaymentCommand(
            user_id=user.id, subscription_tier="pro",
            billing_period="monthly", pay_currency="BTC",
        ))
        assert result.payment_url.startswith("https://")
        order = await payment_repo.get_by_id(result.order_id)
        assert order.status == PaymentOrderStatus.PENDING

        # Step 2: Process webhook (finished)
        process_uc = ProcessWebhookUseCase(
            payment_repo=payment_repo, webhook_log_repo=webhook_log_repo,
            user_repo=user_repo, event_publisher=events,
        )
        await process_uc.execute(WebhookPayload(
            payment_id="ext_100", payment_status="finished",
            order_id=str(result.order_id), pay_amount=0.001,
            pay_currency="BTC", actually_paid=0.001,
            price_amount=29.99, price_currency="USD",
            raw={"payment_id": "ext_100", "payment_status": "finished"},
        ))

        # Verify subscription upgraded
        updated_user = await user_repo.get_by_id(user.id)
        assert updated_user.subscription_tier == SubscriptionTier.PRO

        # Verify order completed
        updated_order = await payment_repo.get_by_id(result.order_id)
        assert updated_order.status == PaymentOrderStatus.FINISHED
        assert updated_order.subscription_activated_at is not None

        # Verify event published
        assert len(events.events) == 1

        # Verify webhook logged
        assert len(webhook_log_repo.logs) == 1

    async def test_idempotent_webhook(self):
        """Processing the same webhook twice should not double-upgrade."""
        user = User(
            id=uuid4(), email=Email("x@x.com"), hashed_password="h",
            role=UserRole.ANALYST, subscription_tier=SubscriptionTier.FREE,
            is_active=True, created_at=datetime.now(timezone.utc),
        )
        user_repo = FakeUserRepo()
        user_repo.add(user)
        payment_repo = FakePaymentRepo()

        order = PaymentOrder(
            id=uuid4(), user_id=user.id, subscription_tier="pro",
            billing_period=BillingPeriod.MONTHLY, amount_usd=Decimal("29.99"),
            external_payment_id="ext_200",
        )
        order = order.mark_finished(Decimal("0.001"), "BTC")
        await payment_repo.save(order)

        process_uc = ProcessWebhookUseCase(
            payment_repo=payment_repo,
            webhook_log_repo=FakeWebhookLogRepo(),
            user_repo=user_repo,
            event_publisher=FakeEventPublisher(),
        )

        # Second webhook for same payment -- should be no-op
        await process_uc.execute(WebhookPayload(
            payment_id="ext_200", payment_status="finished",
            order_id=str(order.id), pay_amount=0.001,
            pay_currency="BTC", actually_paid=0.001,
            price_amount=29.99, price_currency="USD", raw={},
        ))

        # User should still be FREE (idempotency prevented re-processing)
        u = await user_repo.get_by_id(user.id)
        assert u.subscription_tier == SubscriptionTier.FREE
