from dataclasses import dataclass
from uuid import UUID

from src.core.domain.events.base import DomainEvent


@dataclass(frozen=True)
class PaymentReceived(DomainEvent):
    """Raised when a payment is successfully received."""
    payment_id: UUID = None  # type: ignore[assignment]
    user_id: UUID = None  # type: ignore[assignment]
    amount_crypto: str = ""  # str for Decimal serialization safety
    currency: str = ""
    subscription_tier: str = ""


@dataclass(frozen=True)
class PaymentFailed(DomainEvent):
    """Raised when a payment attempt fails."""
    payment_id: UUID = None  # type: ignore[assignment]
    user_id: UUID = None  # type: ignore[assignment]
    error_message: str = ""
