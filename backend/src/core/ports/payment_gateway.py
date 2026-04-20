"""Payment gateway port for crypto payment providers."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


class PaymentStatus:
    """NowPayments status constants."""
    WAITING = "waiting"
    CONFIRMING = "confirming"
    CONFIRMED = "confirmed"
    SENDING = "sending"
    PARTIALLY_PAID = "partially_paid"
    FINISHED = "finished"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass(frozen=True)
class PaymentData:
    """Response from creating a payment via the gateway."""
    payment_id: str
    payment_url: str
    pay_amount: Decimal
    pay_currency: str
    price_amount: Decimal
    price_currency: str
    expiration_estimate_date: str | None = None


class IPaymentGateway(Protocol):
    async def create_invoice(
        self,
        price_amount: Decimal,
        price_currency: str,
        pay_currency: str,
        order_id: str,
        order_description: str,
        ipn_callback_url: str,
        success_url: str,
        cancel_url: str,
    ) -> PaymentData: ...

    async def verify_webhook_signature(self, payload: bytes, signature: str) -> bool: ...

    async def get_payment_status(self, payment_id: str) -> dict: ...

    async def get_supported_currencies(self) -> list[str]: ...
