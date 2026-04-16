"""Use case: process an incoming payment webhook."""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import structlog

from src.core.domain.entities.payment import PaymentOrderStatus, PaymentWebhookLog
from src.core.domain.entities.types import SubscriptionTier
from src.core.domain.pricing import get_duration
from src.core.ports.event_publisher import IEventPublisher
from src.core.ports.payment_repository import IPaymentOrderRepository, IPaymentWebhookLogRepository
from src.core.ports.repositories import IUserRepository

log = structlog.get_logger()


@dataclass
class WebhookPayload:
    payment_id: str
    payment_status: str
    order_id: str
    pay_amount: float
    pay_currency: str
    actually_paid: float
    price_amount: float
    price_currency: str
    raw: dict[str, Any]


class ProcessWebhookUseCase:
    """Process a verified payment webhook from NowPayments.

    Only "finished" status activates a subscription.
    "partially_paid" is logged but not activated.
    """

    def __init__(
        self,
        payment_repo: IPaymentOrderRepository,
        webhook_log_repo: IPaymentWebhookLogRepository,
        user_repo: IUserRepository,
        event_publisher: IEventPublisher,
    ) -> None:
        self._payment_repo = payment_repo
        self._webhook_log_repo = webhook_log_repo
        self._user_repo = user_repo
        self._event_publisher = event_publisher

    async def execute(self, payload: WebhookPayload) -> None:
        # Log the webhook for audit
        webhook_log = PaymentWebhookLog(
            id=uuid4(),
            payment_order_id=UUID(payload.order_id) if payload.order_id else None,
            external_payment_id=payload.payment_id,
            status=payload.payment_status,
            payload=payload.raw,
            signature_valid=True,
        )
        await self._webhook_log_repo.save(webhook_log)

        # Idempotency check
        if await self._payment_repo.is_processed(payload.payment_id):
            log.info("Webhook already processed", payment_id=payload.payment_id)
            return

        # Find the order
        order = await self._payment_repo.get_by_id(UUID(payload.order_id))
        if order is None:
            log.warning("Order not found for webhook", order_id=payload.order_id)
            return

        # Update order status
        status_map = {
            "waiting": PaymentOrderStatus.WAITING,
            "confirming": PaymentOrderStatus.CONFIRMING,
            "confirmed": PaymentOrderStatus.CONFIRMED,
            "sending": PaymentOrderStatus.SENDING,
            "partially_paid": PaymentOrderStatus.PARTIALLY_PAID,
            "finished": PaymentOrderStatus.FINISHED,
            "failed": PaymentOrderStatus.FAILED,
            "expired": PaymentOrderStatus.EXPIRED,
        }
        new_status = status_map.get(payload.payment_status)
        if new_status:
            order.status = new_status
            order.external_payment_id = payload.payment_id

        if payload.payment_status == "finished":
            order = order.mark_finished(
                amount_crypto=Decimal(str(payload.actually_paid)),
                currency=payload.pay_currency,
            )

            # Calculate subscription expiry
            duration = get_duration(order.subscription_tier, order.billing_period.value)
            expires_at = datetime.now(timezone.utc) + duration
            order = order.activate_subscription(expires_at)

            # Upgrade user tier
            tier = SubscriptionTier.PRO if "pro" in order.subscription_tier else SubscriptionTier.ENTERPRISE
            user = await self._user_repo.get_by_id(order.user_id)
            if user is not None:
                upgraded = user.upgrade_subscription(tier)
                await self._user_repo.save(upgraded)
                log.info("Subscription activated", user_id=str(order.user_id), tier=tier.value, expires_at=str(expires_at))

            # Publish event
            from src.core.domain.events.payment import PaymentReceived
            await self._event_publisher.publish(PaymentReceived(
                payment_id=uuid4(),
                user_id=order.user_id,
                amount_crypto=str(payload.actually_paid),
                currency=payload.pay_currency,
                subscription_tier=order.subscription_tier,
            ))

        await self._payment_repo.save(order)
        log.info("Webhook processed", payment_id=payload.payment_id, status=payload.payment_status)
