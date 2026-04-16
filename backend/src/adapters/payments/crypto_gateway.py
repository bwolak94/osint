"""NowPayments gateway adapter for crypto payments."""

import hashlib
import hmac
import json
from decimal import Decimal
from typing import Any

import structlog

from src.core.ports.payment_gateway import IPaymentGateway, PaymentData

log = structlog.get_logger()


class NowPaymentsGateway:
    """NowPayments API integration for crypto payment processing.

    Supports 200+ cryptocurrencies. Uses HMAC-SHA512 for webhook verification.
    Sandbox URL: https://api-sandbox.nowpayments.io/v1
    Production URL: https://api.nowpayments.io/v1
    """

    def __init__(self, api_key: str, ipn_secret: str, sandbox: bool = False) -> None:
        self._api_key = api_key
        self._ipn_secret = ipn_secret
        self._base_url = (
            "https://api-sandbox.nowpayments.io/v1" if sandbox
            else "https://api.nowpayments.io/v1"
        )

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
    ) -> PaymentData:
        try:
            import httpx
        except ImportError:
            log.warning("httpx not installed, returning stub payment")
            return PaymentData(
                payment_id=f"stub_{order_id}",
                payment_url=f"https://nowpayments.io/payment/stub_{order_id}",
                pay_amount=Decimal("0"),
                pay_currency=pay_currency,
                price_amount=price_amount,
                price_currency=price_currency,
            )

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self._base_url}/invoice",
                json={
                    "price_amount": float(price_amount),
                    "price_currency": price_currency.upper(),
                    "pay_currency": pay_currency.upper(),
                    "order_id": order_id,
                    "order_description": order_description,
                    "ipn_callback_url": ipn_callback_url,
                    "success_url": success_url,
                    "cancel_url": cancel_url,
                },
                headers={"x-api-key": self._api_key, "Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()

        return PaymentData(
            payment_id=str(data.get("id", "")),
            payment_url=data.get("invoice_url", ""),
            pay_amount=Decimal(str(data.get("pay_amount", 0))),
            pay_currency=data.get("pay_currency", pay_currency),
            price_amount=price_amount,
            price_currency=price_currency,
            expiration_estimate_date=data.get("expiration_estimate_date"),
        )

    async def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify HMAC-SHA512 signature from NowPayments webhook.

        CRITICAL: Always use constant-time comparison to prevent timing attacks.
        """
        if not signature or not self._ipn_secret:
            return False

        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return False

        # NowPayments requires sorted keys for signature computation
        sorted_payload = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
        expected = hmac.new(
            self._ipn_secret.encode(),
            sorted_payload,
            hashlib.sha512,
        ).hexdigest()

        return hmac.compare_digest(expected, signature)

    async def get_payment_status(self, payment_id: str) -> dict:
        try:
            import httpx
        except ImportError:
            return {"payment_id": payment_id, "payment_status": "pending"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self._base_url}/payment/{payment_id}",
                headers={"x-api-key": self._api_key},
            )
            resp.raise_for_status()
            return resp.json()

    async def get_supported_currencies(self) -> list[str]:
        try:
            import httpx
        except ImportError:
            return ["BTC", "ETH", "USDT", "SOL", "MATIC", "DOGE", "LTC"]

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self._base_url}/currencies",
                headers={"x-api-key": self._api_key},
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("currencies", [])
