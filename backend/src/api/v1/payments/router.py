"""Payment endpoints for crypto subscriptions."""

import json
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.payment_repository import SqlAlchemyPaymentOrderRepository, SqlAlchemyPaymentWebhookLogRepository
from src.adapters.payments.crypto_gateway import NowPaymentsGateway
from src.api.v1.auth.dependencies import get_current_user
from src.api.v1.payments.schemas import (
    CreatePaymentRequest,
    CreatePaymentResponse,
    CurrenciesResponse,
    MessageResponse,
    NowPaymentsWebhookPayload,
    PaymentHistoryResponse,
    PaymentStatusResponse,
)
from src.config import get_settings
from src.core.domain.entities.user import User
from src.dependencies import get_db

router = APIRouter()


def _get_gateway() -> NowPaymentsGateway:
    settings = get_settings()
    return NowPaymentsGateway(
        api_key=settings.nowpayments_api_key,
        ipn_secret=settings.nowpayments_ipn_secret,
        sandbox=settings.nowpayments_sandbox,
    )


@router.post("/create", response_model=CreatePaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
    body: CreatePaymentRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CreatePaymentResponse:
    from src.core.use_cases.payments.create_payment import CreatePaymentCommand, CreatePaymentUseCase

    settings = get_settings()
    payment_repo = SqlAlchemyPaymentOrderRepository(db)
    gateway = _get_gateway()

    use_case = CreatePaymentUseCase(
        payment_repo=payment_repo,
        gateway=gateway,
        base_url=settings.base_url,
        frontend_url=settings.frontend_url,
    )

    result = await use_case.execute(CreatePaymentCommand(
        user_id=current_user.id,
        subscription_tier=body.subscription_tier,
        billing_period=body.billing_period,
        pay_currency=body.pay_currency,
    ))

    return CreatePaymentResponse(
        order_id=result.order_id,
        payment_url=result.payment_url,
        payment_id=result.payment_id,
        amount_usd=result.amount_usd,
        pay_currency=result.pay_currency,
        expires_at=result.expires_at,
    )


@router.post("/webhook")
async def payment_webhook(request: Request, db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    """Handle NowPayments IPN callback.

    This endpoint is PUBLIC (no JWT auth).
    Security is provided by HMAC-SHA512 signature verification.
    """
    payload_bytes = await request.body()
    signature = request.headers.get("x-nowpayments-sig", "")

    gateway = _get_gateway()
    if not await gateway.verify_webhook_signature(payload_bytes, signature):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    data = json.loads(payload_bytes)
    webhook = NowPaymentsWebhookPayload(**data)

    # Idempotency check
    payment_repo = SqlAlchemyPaymentOrderRepository(db)
    if await payment_repo.is_processed(str(webhook.payment_id)):
        return {"status": "already_processed"}

    # Process webhook
    from src.adapters.db.repositories import SqlAlchemyUserRepository
    from src.core.use_cases.payments.process_webhook import ProcessWebhookUseCase, WebhookPayload

    # NoOp event publisher
    class _NoOp:
        async def publish(self, e): pass
        async def publish_many(self, e): pass

    webhook_log_repo = SqlAlchemyPaymentWebhookLogRepository(db)
    user_repo = SqlAlchemyUserRepository(db)

    use_case = ProcessWebhookUseCase(
        payment_repo=payment_repo,
        webhook_log_repo=webhook_log_repo,
        user_repo=user_repo,
        event_publisher=_NoOp(),
    )

    await use_case.execute(WebhookPayload(
        payment_id=str(webhook.payment_id),
        payment_status=webhook.payment_status,
        order_id=webhook.order_id or "",
        pay_amount=webhook.pay_amount,
        pay_currency=webhook.pay_currency or "",
        actually_paid=webhook.actually_paid,
        price_amount=webhook.price_amount,
        price_currency=webhook.price_currency or "USD",
        raw=data,
    ))

    return {"status": "processed"}


@router.get("/status/{order_id}", response_model=PaymentStatusResponse)
async def payment_status(
    order_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PaymentStatusResponse:
    from uuid import UUID
    payment_repo = SqlAlchemyPaymentOrderRepository(db)
    order = await payment_repo.get_by_id(UUID(order_id))
    if order is None or order.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Payment order not found")

    return PaymentStatusResponse(
        order_id=order.id,
        status=order.status.value,
        subscription_tier=order.subscription_tier,
        amount_usd=order.amount_usd,
        amount_crypto=order.amount_crypto,
        crypto_currency=order.crypto_currency,
        subscription_activated_at=order.subscription_activated_at,
        subscription_expires_at=order.subscription_expires_at,
        created_at=order.created_at,
    )


@router.get("/history", response_model=PaymentHistoryResponse)
async def payment_history(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PaymentHistoryResponse:
    payment_repo = SqlAlchemyPaymentOrderRepository(db)
    orders = await payment_repo.get_by_user(current_user.id)
    return PaymentHistoryResponse(
        payments=[
            PaymentStatusResponse(
                order_id=o.id, status=o.status.value, subscription_tier=o.subscription_tier,
                amount_usd=o.amount_usd, amount_crypto=o.amount_crypto,
                crypto_currency=o.crypto_currency,
                subscription_activated_at=o.subscription_activated_at,
                subscription_expires_at=o.subscription_expires_at,
                created_at=o.created_at,
            )
            for o in orders
        ],
        total=len(orders),
    )


@router.get("/currencies", response_model=CurrenciesResponse)
async def supported_currencies() -> CurrenciesResponse:
    gateway = _get_gateway()
    currencies = await gateway.get_supported_currencies()
    return CurrenciesResponse(currencies=currencies)
