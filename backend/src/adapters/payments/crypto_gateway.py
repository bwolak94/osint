"""Stub crypto payment gateway implementation.

Ready for integration with a real crypto payment provider.
"""

from typing import Any
from uuid import UUID, uuid4

import structlog

from src.core.ports.payment_gateway import IPaymentGateway

log = structlog.get_logger()


class CryptoPaymentGateway(IPaymentGateway):
    """Stub payment gateway for crypto payments.

    Replace the method bodies with actual provider API calls for production.
    """

    async def create_payment(self, user_id: UUID, amount_usd: float, metadata: dict[str, Any] | None = None) -> str:
        """Create a stub payment and return a mock payment reference."""
        payment_id = str(uuid4())
        log.info(
            "Stub crypto payment created",
            payment_id=payment_id,
            user_id=str(user_id),
            amount_usd=amount_usd,
        )
        return payment_id

    async def verify_payment(self, payment_id: str, payload: dict[str, Any]) -> bool:
        """Verify a payment webhook (stub always returns True)."""
        log.info("Stub payment verification", payment_id=payment_id)
        return True

    async def get_status(self, payment_id: str) -> dict[str, Any]:
        """Return a stub payment status."""
        return {
            "payment_id": payment_id,
            "status": "pending",
            "amount_usd": 0.0,
            "currency": "BTC",
        }
