"""Payment endpoints."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends

from src.api.v1.payments.schemas import CreatePaymentRequest, PaymentStatusResponse, WebhookPayload
from src.adapters.payments.crypto_gateway import CryptoPaymentGateway
from src.dependencies import get_current_user

router = APIRouter()


@router.post("/create", response_model=dict[str, str], status_code=201)
async def create_payment(
    body: CreatePaymentRequest,
    user: Annotated[dict, Depends(get_current_user)],
) -> dict[str, str]:
    """Initiate a new crypto payment."""
    gateway = CryptoPaymentGateway()
    payment_id = await gateway.create_payment(
        user_id=UUID(user["user_id"]),
        amount_usd=body.amount_usd,
        metadata=body.metadata,
    )
    return {"payment_id": payment_id, "status": "created"}


@router.post("/webhook")
async def payment_webhook(payload: WebhookPayload) -> dict[str, str]:
    """Handle an incoming payment webhook from the provider."""
    gateway = CryptoPaymentGateway()
    verified = await gateway.verify_payment(
        payment_id=payload.payment_id,
        payload=payload.data,
    )
    return {"verified": str(verified)}


@router.get("/status/{payment_id}", response_model=PaymentStatusResponse)
async def payment_status(
    payment_id: str,
    user: Annotated[dict, Depends(get_current_user)],
) -> PaymentStatusResponse:
    """Check the status of a payment."""
    gateway = CryptoPaymentGateway()
    result = await gateway.get_status(payment_id)
    return PaymentStatusResponse(**result)
