"""Payment-related domain entities."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID


class PaymentOrderStatus(str, Enum):
    PENDING = "pending"
    WAITING = "waiting"
    CONFIRMING = "confirming"
    CONFIRMED = "confirmed"
    SENDING = "sending"
    PARTIALLY_PAID = "partially_paid"
    FINISHED = "finished"
    FAILED = "failed"
    EXPIRED = "expired"
    REFUNDED = "refunded"


class BillingPeriod(str, Enum):
    MONTHLY = "monthly"
    YEARLY = "yearly"


@dataclass
class PaymentOrder:
    """Represents a single payment transaction."""

    id: UUID
    user_id: UUID
    subscription_tier: str  # "pro" or "enterprise"
    billing_period: BillingPeriod
    amount_usd: Decimal
    amount_crypto: Decimal | None = None
    crypto_currency: str | None = None
    external_payment_id: str | None = None
    payment_url: str | None = None
    status: PaymentOrderStatus = PaymentOrderStatus.PENDING
    subscription_activated_at: datetime | None = None
    subscription_expires_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def mark_finished(self, amount_crypto: Decimal, currency: str) -> PaymentOrder:
        """Mark as finished and record crypto amount."""
        return replace(
            self,
            status=PaymentOrderStatus.FINISHED,
            amount_crypto=amount_crypto,
            crypto_currency=currency,
            updated_at=datetime.now(timezone.utc),
        )

    def activate_subscription(self, expires_at: datetime) -> PaymentOrder:
        """Activate the subscription after successful payment."""
        return replace(
            self,
            subscription_activated_at=datetime.now(timezone.utc),
            subscription_expires_at=expires_at,
            updated_at=datetime.now(timezone.utc),
        )

    def mark_failed(self) -> PaymentOrder:
        return replace(self, status=PaymentOrderStatus.FAILED, updated_at=datetime.now(timezone.utc))

    def mark_expired(self) -> PaymentOrder:
        return replace(self, status=PaymentOrderStatus.EXPIRED, updated_at=datetime.now(timezone.utc))

    @property
    def is_completed(self) -> bool:
        return self.status == PaymentOrderStatus.FINISHED


@dataclass
class PaymentWebhookLog:
    """Audit log entry for incoming webhooks."""

    id: UUID
    payment_order_id: UUID | None
    external_payment_id: str
    status: str
    payload: dict[str, Any]
    signature_valid: bool
    processed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
