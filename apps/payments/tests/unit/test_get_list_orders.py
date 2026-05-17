"""Unit tests for GetOrderUseCase and ListMyOrdersUseCase."""

from __future__ import annotations

import uuid

import pytest

from apps.payments.application.use_cases.get_order import GetOrderUseCase
from apps.payments.application.use_cases.list_my_orders import ListMyOrdersUseCase
from apps.payments.domain.exceptions import OrderNotFoundError
from apps.payments.tests.unit.fakes import FakePaymentOrderRepository, make_order


def test_get_order_returns_own_order():
    """GetOrderUseCase returns the order when user_id matches."""
    order = make_order()
    repo = FakePaymentOrderRepository([order])
    result = GetOrderUseCase(repo).execute(order_id=order.id, user_id=order.user_id)
    assert result.id == order.id


def test_get_order_wrong_user_raises():
    """GetOrderUseCase raises OrderNotFoundError when user_id does not match."""
    order = make_order()
    repo = FakePaymentOrderRepository([order])
    with pytest.raises(OrderNotFoundError):
        GetOrderUseCase(repo).execute(order_id=order.id, user_id=uuid.uuid4())


def test_get_order_missing_raises():
    """GetOrderUseCase raises OrderNotFoundError when order does not exist."""
    repo = FakePaymentOrderRepository()
    with pytest.raises(OrderNotFoundError):
        GetOrderUseCase(repo).execute(order_id=uuid.uuid4(), user_id=uuid.uuid4())


def test_list_my_orders_returns_own_orders():
    """ListMyOrdersUseCase returns only orders owned by the user."""
    user_id = uuid.uuid4()
    own = [make_order(user_id=user_id) for _ in range(3)]
    other = make_order()
    repo = FakePaymentOrderRepository(own + [other])
    results = ListMyOrdersUseCase(repo).execute(user_id=user_id)
    assert len(results) == 3
    assert all(r.user_id == user_id for r in results)


def test_list_my_orders_empty():
    """ListMyOrdersUseCase returns empty list when user has no orders."""
    repo = FakePaymentOrderRepository()
    assert ListMyOrdersUseCase(repo).execute(user_id=uuid.uuid4()) == []
