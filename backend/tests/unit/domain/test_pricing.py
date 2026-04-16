"""Tests for subscription pricing."""

import pytest
from decimal import Decimal

from src.core.domain.pricing import get_price, get_duration


class TestPricing:
    def test_pro_monthly_price(self):
        assert get_price("pro", "monthly") == Decimal("29.99")

    def test_pro_yearly_price(self):
        assert get_price("pro", "yearly") == Decimal("299.99")

    def test_enterprise_monthly_price(self):
        assert get_price("enterprise", "monthly") == Decimal("99.99")

    def test_enterprise_yearly_price(self):
        assert get_price("enterprise", "yearly") == Decimal("999.99")

    def test_invalid_tier_raises(self):
        with pytest.raises(ValueError):
            get_price("invalid", "monthly")

    def test_pro_monthly_duration(self):
        d = get_duration("pro", "monthly")
        assert d.days == 31

    def test_yearly_duration(self):
        d = get_duration("pro", "yearly")
        assert d.days == 366
