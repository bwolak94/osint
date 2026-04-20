"""Subscription pricing configuration."""

from datetime import timedelta
from decimal import Decimal

SUBSCRIPTION_PRICES: dict[str, Decimal] = {
    "pro_monthly": Decimal("29.99"),
    "pro_yearly": Decimal("299.99"),
    "enterprise_monthly": Decimal("99.99"),
    "enterprise_yearly": Decimal("999.99"),
}

SUBSCRIPTION_DURATIONS: dict[str, timedelta] = {
    "pro_monthly": timedelta(days=31),
    "pro_yearly": timedelta(days=366),
    "enterprise_monthly": timedelta(days=31),
    "enterprise_yearly": timedelta(days=366),
}


def get_price(tier: str, period: str) -> Decimal:
    """Get price for a subscription tier and billing period."""
    key = f"{tier}_{period}"
    if key not in SUBSCRIPTION_PRICES:
        raise ValueError(f"Unknown subscription plan: {key}")
    return SUBSCRIPTION_PRICES[key]


def get_duration(tier: str, period: str) -> timedelta:
    """Get duration for a subscription tier and billing period."""
    key = f"{tier}_{period}"
    if key not in SUBSCRIPTION_DURATIONS:
        raise ValueError(f"Unknown subscription plan: {key}")
    return SUBSCRIPTION_DURATIONS[key]
