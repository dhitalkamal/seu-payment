"""Unit tests for ProcessWebhookUseCase."""

from __future__ import annotations

import pytest

from apps.payments.application.use_cases.process_webhook import ProcessWebhookUseCase
from apps.payments.domain.exceptions import OrderNotFoundError
from apps.payments.tests.unit.fakes import FakePaymentOrderRepository, make_order


def test_webhook_success_sets_completed():
    """A successful webhook payload transitions the order to completed."""
    order = make_order(status="processing", gateway_order_id="gw_123")
    repo = FakePaymentOrderRepository([order])
    result = ProcessWebhookUseCase(repo).execute(
        gateway_order_id="gw_123",
        status="completed",
        gateway_transaction_id="txn_abc",
    )
    assert result.status == "completed"
    assert result.completed_at is not None
    assert result.gateway_order_id == "gw_123"


def test_webhook_failure_sets_failed():
    """A failed webhook payload transitions the order to failed."""
    order = make_order(status="processing", gateway_order_id="gw_456")
    repo = FakePaymentOrderRepository([order])
    result = ProcessWebhookUseCase(repo).execute(
        gateway_order_id="gw_456",
        status="failed",
        gateway_transaction_id="",
    )
    assert result.status == "failed"


def test_webhook_unknown_order_raises():
    """Raises OrderNotFoundError when no order matches the gateway_order_id."""
    repo = FakePaymentOrderRepository()
    with pytest.raises(OrderNotFoundError):
        ProcessWebhookUseCase(repo).execute(
            gateway_order_id="nonexistent",
            status="completed",
            gateway_transaction_id="txn_x",
        )


def test_webhook_already_completed_is_noop():
    """A duplicate webhook on an already completed order returns without changes."""
    order = make_order(status="completed", gateway_order_id="gw_789")
    repo = FakePaymentOrderRepository([order])
    result = ProcessWebhookUseCase(repo).execute(
        gateway_order_id="gw_789",
        status="completed",
        gateway_transaction_id="txn_dup",
    )
    assert result.status == "completed"
