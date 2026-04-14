from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Protocol
from uuid import UUID

from src.core.domain.entities.types import SubscriptionTier


class PaymentStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass(frozen=True)
class PaymentIntent:
    payment_id: str
    payment_url: str
    amount_usd: Decimal
    crypto_amount: Decimal | None
    crypto_currency: str | None
    expires_at: str  # ISO format


class IPaymentGateway(Protocol):
    async def create_payment(
        self, amount_usd: Decimal, user_id: UUID, tier: SubscriptionTier
    ) -> PaymentIntent: ...

    async def verify_payment(self, payment_id: str) -> PaymentStatus: ...

    async def get_supported_currencies(self) -> list[str]: ...
