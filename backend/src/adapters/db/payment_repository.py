"""SQLAlchemy implementation of payment repositories."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.db.payment_models import PaymentOrderModel, PaymentWebhookLogModel
from src.core.domain.entities.payment import BillingPeriod, PaymentOrder, PaymentOrderStatus, PaymentWebhookLog


class SqlAlchemyPaymentOrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, order: PaymentOrder) -> PaymentOrder:
        model = await self._session.get(PaymentOrderModel, order.id)
        if model is not None:
            model.status = order.status.value
            model.amount_crypto = order.amount_crypto
            model.crypto_currency = order.crypto_currency
            model.external_payment_id = order.external_payment_id
            model.payment_url = order.payment_url
            model.subscription_activated_at = order.subscription_activated_at
            model.subscription_expires_at = order.subscription_expires_at
            model.updated_at = datetime.now(timezone.utc)
        else:
            model = PaymentOrderModel(
                id=order.id,
                user_id=order.user_id,
                subscription_tier=order.subscription_tier,
                billing_period=order.billing_period.value,
                amount_usd=order.amount_usd,
                amount_crypto=order.amount_crypto,
                crypto_currency=order.crypto_currency,
                external_payment_id=order.external_payment_id,
                payment_url=order.payment_url,
                status=order.status.value,
                subscription_activated_at=order.subscription_activated_at,
                subscription_expires_at=order.subscription_expires_at,
            )
            self._session.add(model)
        await self._session.flush()
        return order

    async def get_by_id(self, order_id: UUID) -> PaymentOrder | None:
        model = await self._session.get(PaymentOrderModel, order_id)
        return self._to_entity(model) if model else None

    async def get_by_external_id(self, external_id: str) -> PaymentOrder | None:
        stmt = select(PaymentOrderModel).where(PaymentOrderModel.external_payment_id == external_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_user(self, user_id: UUID) -> list[PaymentOrder]:
        stmt = (
            select(PaymentOrderModel)
            .where(PaymentOrderModel.user_id == user_id)
            .order_by(PaymentOrderModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def is_processed(self, external_payment_id: str) -> bool:
        order = await self.get_by_external_id(external_payment_id)
        return order is not None and order.status == PaymentOrderStatus.FINISHED

    @staticmethod
    def _to_entity(model: PaymentOrderModel) -> PaymentOrder:
        return PaymentOrder(
            id=model.id,
            user_id=model.user_id,
            subscription_tier=model.subscription_tier,
            billing_period=BillingPeriod(model.billing_period),
            amount_usd=model.amount_usd,
            amount_crypto=model.amount_crypto,
            crypto_currency=model.crypto_currency,
            external_payment_id=model.external_payment_id,
            payment_url=model.payment_url,
            status=PaymentOrderStatus(model.status),
            subscription_activated_at=model.subscription_activated_at,
            subscription_expires_at=model.subscription_expires_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


class SqlAlchemyPaymentWebhookLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, log_entry: PaymentWebhookLog) -> PaymentWebhookLog:
        model = PaymentWebhookLogModel(
            id=log_entry.id,
            payment_order_id=log_entry.payment_order_id,
            external_payment_id=log_entry.external_payment_id,
            status=log_entry.status,
            payload=log_entry.payload,
            signature_valid=log_entry.signature_valid,
        )
        self._session.add(model)
        await self._session.flush()
        return log_entry
