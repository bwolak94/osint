"""Use case: create a new crypto payment order."""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import structlog

from src.core.domain.entities.payment import BillingPeriod, PaymentOrder
from src.core.domain.pricing import get_duration, get_price
from src.core.ports.payment_gateway import IPaymentGateway
from src.core.ports.payment_repository import IPaymentOrderRepository

log = structlog.get_logger()


@dataclass
class CreatePaymentCommand:
    user_id: UUID
    subscription_tier: str  # "pro" or "enterprise"
    billing_period: str  # "monthly" or "yearly"
    pay_currency: str  # "BTC", "ETH", "USDT", etc.


@dataclass
class CreatePaymentResult:
    order_id: UUID
    payment_url: str
    payment_id: str
    amount_usd: Decimal
    pay_currency: str
    expires_at: str | None


class CreatePaymentUseCase:
    def __init__(
        self,
        payment_repo: IPaymentOrderRepository,
        gateway: IPaymentGateway,
        base_url: str,
        frontend_url: str,
    ) -> None:
        self._payment_repo = payment_repo
        self._gateway = gateway
        self._base_url = base_url
        self._frontend_url = frontend_url

    async def execute(self, command: CreatePaymentCommand) -> CreatePaymentResult:
        price_usd = get_price(command.subscription_tier, command.billing_period)

        order = PaymentOrder(
            id=uuid4(),
            user_id=command.user_id,
            subscription_tier=command.subscription_tier,
            billing_period=BillingPeriod(command.billing_period),
            amount_usd=price_usd,
        )
        await self._payment_repo.save(order)

        payment = await self._gateway.create_invoice(
            price_amount=price_usd,
            price_currency="USD",
            pay_currency=command.pay_currency,
            order_id=str(order.id),
            order_description=f"OSINT Platform — {command.subscription_tier} {command.billing_period}",
            ipn_callback_url=f"{self._base_url}/api/v1/payments/webhook",
            success_url=f"{self._frontend_url}/payments/success",
            cancel_url=f"{self._frontend_url}/payments/cancel",
        )

        # Update order with external payment info
        order.external_payment_id = payment.payment_id
        order.payment_url = payment.payment_url
        await self._payment_repo.save(order)

        log.info("Payment created", order_id=str(order.id), tier=command.subscription_tier, amount=str(price_usd))

        return CreatePaymentResult(
            order_id=order.id,
            payment_url=payment.payment_url,
            payment_id=payment.payment_id,
            amount_usd=price_usd,
            pay_currency=command.pay_currency,
            expires_at=payment.expiration_estimate_date,
        )
