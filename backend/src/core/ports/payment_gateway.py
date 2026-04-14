"""Abstract payment gateway port."""

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID


class IPaymentGateway(ABC):
    """Port for payment processing."""

    @abstractmethod
    async def create_payment(self, user_id: UUID, amount_usd: float, metadata: dict[str, Any] | None = None) -> str:
        """Initiate a payment and return a payment reference / URL."""
        ...

    @abstractmethod
    async def verify_payment(self, payment_id: str, payload: dict[str, Any]) -> bool:
        """Verify a payment webhook or callback."""
        ...

    @abstractmethod
    async def get_status(self, payment_id: str) -> dict[str, Any]:
        """Check the current status of a payment."""
        ...
