"""Pydantic schemas for payments API."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class CreatePaymentRequest(BaseModel):
    subscription_tier: Literal["pro", "enterprise"]
    billing_period: Literal["monthly", "yearly"] = "monthly"
    pay_currency: str = Field(default="BTC", max_length=10)


class CreatePaymentResponse(BaseModel):
    order_id: UUID
    payment_url: str
    payment_id: str
    amount_usd: Decimal
    pay_currency: str
    expires_at: str | None = None


class PaymentStatusResponse(BaseModel):
    order_id: UUID
    status: str
    subscription_tier: str
    amount_usd: Decimal
    amount_crypto: Decimal | None = None
    crypto_currency: str | None = None
    subscription_activated_at: datetime | None = None
    subscription_expires_at: datetime | None = None
    created_at: datetime


class PaymentHistoryResponse(BaseModel):
    payments: list[PaymentStatusResponse]
    total: int


class CurrenciesResponse(BaseModel):
    currencies: list[str]


class NowPaymentsWebhookPayload(BaseModel):
    payment_id: str | int
    payment_status: str
    order_id: str | None = None
    pay_address: str | None = None
    pay_amount: float = 0
    pay_currency: str | None = None
    actually_paid: float = 0
    price_amount: float = 0
    price_currency: str | None = None
    outcome_amount: float | None = None
    outcome_currency: str | None = None

    class Config:
        extra = "allow"


class MessageResponse(BaseModel):
    message: str
