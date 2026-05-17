"""Unit tests for CreatePaymentOrderUseCase."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from apps.payments.application.use_cases.create_order import CreatePaymentOrderUseCase
from apps.payments.domain.exceptions import InvalidPromoCodeError, OrderAlreadyExistsError
from apps.payments.tests.unit.fakes import (
    FakePaymentOrderRepository,
    FakePromoCodeRepository,
    make_order,
    make_promo,
)


def _uc(orders=None, promo=None) -> CreatePaymentOrderUseCase:
    return CreatePaymentOrderUseCase(
        order_repo=FakePaymentOrderRepository(orders or []),
        promo_repo=FakePromoCodeRepository(promo),
    )


def _defaults(**overrides: object) -> dict:
    base: dict = {
        "user_id": uuid.uuid4(),
        "event_id": uuid.uuid4(),
        "registration_id": uuid.uuid4(),
        "subtotal": Decimal("1000.00"),
        "gateway": "khalti",
        "idempotency_key": uuid.uuid4(),
        "promo_code": None,
    }
    base.update(overrides)
    return base


def test_create_order_correct_fees():
    """Platform fee is 5% of subtotal and total equals subtotal plus platform fee."""
    result = _uc().execute(**_defaults(subtotal=Decimal("1000.00")))
    assert result.platform_fee == Decimal("50.00")
    assert result.total_amount == Decimal("1050.00")
    assert result.discount_amount == Decimal("0.00")
    assert result.status == "created"


def test_create_order_idempotency_returns_existing():
    """Reusing the same idempotency_key returns the existing order unchanged."""
    key = uuid.uuid4()
    existing = make_order(idempotency_key=key)
    result = _uc(orders=[existing]).execute(**_defaults(idempotency_key=key))
    assert result.id == existing.id


def test_create_order_duplicate_registration_raises():
    """A second order for the same registration raises OrderAlreadyExistsError."""
    reg_id = uuid.uuid4()
    existing = make_order(registration_id=reg_id)
    with pytest.raises(OrderAlreadyExistsError):
        _uc(orders=[existing]).execute(**_defaults(registration_id=reg_id))


def test_create_order_percentage_promo_applies():
    """A 10% promo on 1000 gives discount=100, platform_fee=50, total=950."""
    promo = make_promo(discount_type="percentage", discount_value=Decimal("10"))
    result = _uc(promo=promo).execute(**_defaults(promo_code="SAVE10"))
    assert result.discount_amount == Decimal("100.00")
    assert result.platform_fee == Decimal("50.00")
    assert result.total_amount == Decimal("950.00")


def test_create_order_expired_promo_raises():
    """An expired promo raises InvalidPromoCodeError."""
    promo = make_promo(valid_until=datetime.now(timezone.utc) - timedelta(hours=1))
    with pytest.raises(InvalidPromoCodeError):
        _uc(promo=promo).execute(**_defaults(promo_code="SAVE10"))


def test_create_order_exhausted_promo_raises():
    """A fully used promo raises InvalidPromoCodeError."""
    promo = make_promo(max_usage_count=10, used_count=10)
    with pytest.raises(InvalidPromoCodeError):
        _uc(promo=promo).execute(**_defaults(promo_code="SAVE10"))


def test_create_order_fee_formula():
    """total_amount always equals subtotal minus discount_amount plus platform_fee."""
    subtotal = Decimal("2000.00")
    result = _uc().execute(**_defaults(subtotal=subtotal))
    assert result.total_amount == result.subtotal - result.discount_amount + result.platform_fee
