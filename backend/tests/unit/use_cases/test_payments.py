"""Tests for payment use cases."""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from src.core.domain.entities.payment import BillingPeriod, PaymentOrder, PaymentOrderStatus, PaymentWebhookLog
from src.core.domain.entities.user import User
from src.core.domain.entities.types import UserRole, SubscriptionTier
from src.core.domain.value_objects.email import Email
from src.core.use_cases.payments.create_payment import CreatePaymentCommand, CreatePaymentUseCase
from src.core.use_cases.payments.process_webhook import ProcessWebhookUseCase, WebhookPayload
from src.core.ports.payment_gateway import PaymentData


class FakePaymentRepo:
    def __init__(self):
        self._orders = {}
        self._by_external = {}

    async def save(self, order):
        self._orders[order.id] = order
        if order.external_payment_id:
            self._by_external[order.external_payment_id] = order
        return order

    async def get_by_id(self, order_id):
        return self._orders.get(order_id)

    async def get_by_external_id(self, external_id):
        return self._by_external.get(external_id)

    async def get_by_user(self, user_id):
        return [o for o in self._orders.values() if o.user_id == user_id]

    async def is_processed(self, external_payment_id):
        order = self._by_external.get(external_payment_id)
        return order is not None and order.status == PaymentOrderStatus.FINISHED


class FakeWebhookLogRepo:
    def __init__(self):
        self.logs = []

    async def save(self, log):
        self.logs.append(log)
        return log


class FakeGateway:
    def __init__(self):
        self.last_request = None

    async def create_invoice(self, **kwargs):
        self.last_request = kwargs
        return PaymentData(
            payment_id="ext_123",
            payment_url="https://nowpayments.io/pay/ext_123",
            pay_amount=Decimal("0.001"),
            pay_currency=kwargs.get("pay_currency", "BTC"),
            price_amount=kwargs.get("price_amount", Decimal("29.99")),
            price_currency="USD",
            expiration_estimate_date="2026-05-01T00:00:00Z",
        )

    async def verify_webhook_signature(self, payload, signature):
        return True

    async def get_payment_status(self, payment_id):
        return {"payment_id": payment_id, "payment_status": "finished"}

    async def get_supported_currencies(self):
        return ["BTC", "ETH", "USDT"]


class FakeUserRepo:
    def __init__(self):
        self._users = {}

    async def get_by_id(self, user_id):
        return self._users.get(user_id)

    async def get_by_email(self, email):
        return None

    async def save(self, user):
        self._users[user.id] = user
        return user

    async def delete(self, uid):
        pass

    def add(self, user):
        self._users[user.id] = user


class FakeEventPublisher:
    def __init__(self):
        self.events = []

    async def publish(self, event):
        self.events.append(event)

    async def publish_many(self, events):
        self.events.extend(events)


class TestCreatePayment:
    async def test_creates_order_and_returns_url(self):
        repo = FakePaymentRepo()
        gateway = FakeGateway()
        uc = CreatePaymentUseCase(
            payment_repo=repo, gateway=gateway,
            base_url="http://localhost:8000", frontend_url="http://localhost:5173",
        )
        result = await uc.execute(CreatePaymentCommand(
            user_id=uuid4(), subscription_tier="pro", billing_period="monthly", pay_currency="BTC",
        ))
        assert result.payment_url.startswith("https://")
        assert result.amount_usd == Decimal("29.99")
        assert result.payment_id == "ext_123"

    async def test_order_persisted_in_repo(self):
        repo = FakePaymentRepo()
        gateway = FakeGateway()
        uc = CreatePaymentUseCase(
            payment_repo=repo, gateway=gateway,
            base_url="http://localhost:8000", frontend_url="http://localhost:5173",
        )
        result = await uc.execute(CreatePaymentCommand(
            user_id=uuid4(), subscription_tier="pro", billing_period="monthly", pay_currency="ETH",
        ))
        order = await repo.get_by_id(result.order_id)
        assert order is not None
        assert order.external_payment_id == "ext_123"

    async def test_yearly_price_correct(self):
        repo = FakePaymentRepo()
        gateway = FakeGateway()
        uc = CreatePaymentUseCase(
            payment_repo=repo, gateway=gateway,
            base_url="http://localhost:8000", frontend_url="http://localhost:5173",
        )
        result = await uc.execute(CreatePaymentCommand(
            user_id=uuid4(), subscription_tier="pro", billing_period="yearly", pay_currency="BTC",
        ))
        assert result.amount_usd == Decimal("299.99")

    async def test_enterprise_price(self):
        repo = FakePaymentRepo()
        gateway = FakeGateway()
        uc = CreatePaymentUseCase(
            payment_repo=repo, gateway=gateway,
            base_url="http://localhost:8000", frontend_url="http://localhost:5173",
        )
        result = await uc.execute(CreatePaymentCommand(
            user_id=uuid4(), subscription_tier="enterprise", billing_period="monthly", pay_currency="USDT",
        ))
        assert result.amount_usd == Decimal("99.99")

    async def test_invalid_tier_raises(self):
        repo = FakePaymentRepo()
        gateway = FakeGateway()
        uc = CreatePaymentUseCase(
            payment_repo=repo, gateway=gateway,
            base_url="http://localhost:8000", frontend_url="http://localhost:5173",
        )
        with pytest.raises(ValueError):
            await uc.execute(CreatePaymentCommand(
                user_id=uuid4(), subscription_tier="invalid", billing_period="monthly", pay_currency="BTC",
            ))


class TestProcessWebhook:
    def _make_deps(self):
        user = User(
            id=uuid4(), email=Email("user@example.com"), hashed_password="h",
            role=UserRole.ANALYST, subscription_tier=SubscriptionTier.FREE,
            is_active=True, created_at=datetime.now(timezone.utc),
        )
        user_repo = FakeUserRepo()
        user_repo.add(user)

        order = PaymentOrder(
            id=uuid4(), user_id=user.id, subscription_tier="pro",
            billing_period=BillingPeriod.MONTHLY, amount_usd=Decimal("29.99"),
        )
        payment_repo = FakePaymentRepo()

        return {
            "payment_repo": payment_repo,
            "webhook_log_repo": FakeWebhookLogRepo(),
            "user_repo": user_repo,
            "event_publisher": FakeEventPublisher(),
            "order": order,
            "user": user,
        }

    async def test_finished_activates_subscription(self):
        deps = self._make_deps()
        await deps["payment_repo"].save(deps["order"])

        uc = ProcessWebhookUseCase(
            payment_repo=deps["payment_repo"],
            webhook_log_repo=deps["webhook_log_repo"],
            user_repo=deps["user_repo"],
            event_publisher=deps["event_publisher"],
        )
        await uc.execute(WebhookPayload(
            payment_id="ext_pay_1",
            payment_status="finished",
            order_id=str(deps["order"].id),
            pay_amount=0.001,
            pay_currency="BTC",
            actually_paid=0.001,
            price_amount=29.99,
            price_currency="USD",
            raw={"payment_id": "ext_pay_1", "payment_status": "finished"},
        ))

        order = await deps["payment_repo"].get_by_id(deps["order"].id)
        assert order.status == PaymentOrderStatus.FINISHED
        assert order.subscription_activated_at is not None

        user = await deps["user_repo"].get_by_id(deps["user"].id)
        assert user.subscription_tier == SubscriptionTier.PRO

    async def test_failed_does_not_activate(self):
        deps = self._make_deps()
        await deps["payment_repo"].save(deps["order"])

        uc = ProcessWebhookUseCase(
            payment_repo=deps["payment_repo"],
            webhook_log_repo=deps["webhook_log_repo"],
            user_repo=deps["user_repo"],
            event_publisher=deps["event_publisher"],
        )
        await uc.execute(WebhookPayload(
            payment_id="ext_pay_2",
            payment_status="failed",
            order_id=str(deps["order"].id),
            pay_amount=0, pay_currency="BTC", actually_paid=0,
            price_amount=29.99, price_currency="USD",
            raw={"payment_id": "ext_pay_2", "payment_status": "failed"},
        ))

        order = await deps["payment_repo"].get_by_id(deps["order"].id)
        assert order.status == PaymentOrderStatus.FAILED
        assert order.subscription_activated_at is None

    async def test_webhook_logged(self):
        deps = self._make_deps()
        await deps["payment_repo"].save(deps["order"])

        uc = ProcessWebhookUseCase(
            payment_repo=deps["payment_repo"],
            webhook_log_repo=deps["webhook_log_repo"],
            user_repo=deps["user_repo"],
            event_publisher=deps["event_publisher"],
        )
        await uc.execute(WebhookPayload(
            payment_id="ext_1", payment_status="confirming",
            order_id=str(deps["order"].id),
            pay_amount=0, pay_currency="BTC", actually_paid=0,
            price_amount=29.99, price_currency="USD", raw={},
        ))

        assert len(deps["webhook_log_repo"].logs) == 1

    async def test_publishes_payment_event_on_finish(self):
        deps = self._make_deps()
        await deps["payment_repo"].save(deps["order"])

        uc = ProcessWebhookUseCase(
            payment_repo=deps["payment_repo"],
            webhook_log_repo=deps["webhook_log_repo"],
            user_repo=deps["user_repo"],
            event_publisher=deps["event_publisher"],
        )
        await uc.execute(WebhookPayload(
            payment_id="ext_3", payment_status="finished",
            order_id=str(deps["order"].id),
            pay_amount=0.001, pay_currency="ETH", actually_paid=0.001,
            price_amount=29.99, price_currency="USD",
            raw={"payment_id": "ext_3", "payment_status": "finished"},
        ))

        assert len(deps["event_publisher"].events) == 1
