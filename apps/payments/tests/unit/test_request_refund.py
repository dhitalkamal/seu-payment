"""Unit tests for RequestRefundUseCase."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from apps.payments.application.use_cases.request_refund import RequestRefundUseCase
from apps.payments.domain.exceptions import OrderNotFoundError, RefundNotAllowedError
from apps.payments.tests.unit.fakes import (
    FakePaymentOrderRepository,
    FakeRefundRepository,
    make_order,
)


def _uc(orders=None) -> RequestRefundUseCase:
    return RequestRefundUseCase(
        order_repo=FakePaymentOrderRepository(orders or []),
        refund_repo=FakeRefundRepository(),
    )


def test_refund_creates_pending_refund():
    """Successful refund returns a RefundEntity with status=pending."""
    user_id = uuid.uuid4()
    order = make_order(user_id=user_id, status="completed")
    result = _uc(orders=[order]).execute(order_id=order.id, user_id=user_id, reason="Changed my mind")
    assert result.status == "pending"
    assert result.order_id == order.id
    assert result.amount == order.total_amount


def test_refund_sets_order_to_refunded():
    """After refund the order status is set to refunded."""
    user_id = uuid.uuid4()
    order = make_order(user_id=user_id, status="completed")
    repo = FakePaymentOrderRepository([order])
    RequestRefundUseCase(order_repo=repo, refund_repo=FakeRefundRepository()).execute(order_id=order.id, user_id=user_id, reason="Event cancelled")
    updated = repo.get_by_id(order.id, user_id)
    assert updated.status == "refunded"


def test_refund_wrong_owner_raises():
    """Refunding an order you do not own raises OrderNotFoundError."""
    order = make_order(user_id=uuid.uuid4(), status="completed")
    with pytest.raises(OrderNotFoundError):
        _uc(orders=[order]).execute(order_id=order.id, user_id=uuid.uuid4(), reason="Mine")


def test_refund_non_completed_raises():
    """Refunding a created order raises RefundNotAllowedError."""
    user_id = uuid.uuid4()
    order = make_order(user_id=user_id, status="created")
    with pytest.raises(RefundNotAllowedError):
        _uc(orders=[order]).execute(order_id=order.id, user_id=user_id, reason="Test")


def test_refund_no_amount_defaults_to_total():
    """Omitting amount defaults to the full order total."""
    user_id = uuid.uuid4()
    order = make_order(user_id=user_id, status="completed", total_amount=Decimal("1050.00"))
    result = _uc(orders=[order]).execute(order_id=order.id, user_id=user_id, reason="Full refund")
    assert result.amount == Decimal("1050.00")
