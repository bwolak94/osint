"""Payment-related Pydantic schemas."""

from typing import Any

from pydantic import BaseModel


class CreatePaymentRequest(BaseModel):
    """Request body for creating a payment."""

    amount_usd: float
    metadata: dict[str, Any] | None = None


class WebhookPayload(BaseModel):
    """Incoming webhook payload from the payment provider."""

    payment_id: str
    data: dict[str, Any] = {}


class PaymentStatusResponse(BaseModel):
    """Response schema for payment status."""

    payment_id: str
    status: str
    amount_usd: float
    currency: str
