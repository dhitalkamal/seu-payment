"""Unit tests for dispute use cases."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from apps.payments.application.use_cases.create_dispute import CreateDisputeUseCase
from apps.payments.application.use_cases.list_disputes import ListDisputesUseCase
from apps.payments.application.use_cases.update_dispute_status import UpdateDisputeStatusUseCase
from apps.payments.domain.exceptions import DisputeNotFoundError, OrderNotFoundError
from apps.payments.tests.unit.fakes import (
    FakeDisputeRepository,
    FakePaymentOrderRepository,
    make_dispute,
    make_order,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def test_create_dispute_success():
    """Creating a dispute stores it and returns the entity."""
    order = make_order(status="completed")
    orders = FakePaymentOrderRepository([order])
    disputes = FakeDisputeRepository()

    result = CreateDisputeUseCase(orders, disputes).execute(
        order_id=order.id,
        user_id=order.user_id,
        reason="duplicate",
        description="I was charged twice.",
    )

    assert result.order_id == order.id
    assert result.status == "open"
    assert result.reason == "duplicate"


def test_create_dispute_order_not_found():
    """Creating a dispute for a non-existent order raises OrderNotFoundError."""
    disputes = FakeDisputeRepository()
    orders = FakePaymentOrderRepository([])

    with pytest.raises(OrderNotFoundError):
        CreateDisputeUseCase(orders, disputes).execute(
            order_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            reason="duplicate",
            description="test",
        )


def test_list_disputes_returns_user_disputes():
    """Only disputes belonging to the user's orders are returned."""
    order = make_order(status="completed")
    other_order = make_order(status="completed")
    d1 = make_dispute(order_id=order.id, user_id=order.user_id)
    d2 = make_dispute(order_id=other_order.id, user_id=other_order.user_id)
    disputes = FakeDisputeRepository([d1, d2])

    result = ListDisputesUseCase(disputes).execute(order_id=order.id, user_id=order.user_id)

    assert len(result) == 1
    assert result[0].order_id == order.id


def test_update_dispute_status_success():
    """Updating dispute status changes the status field."""
    order = make_order(status="completed")
    dispute = make_dispute(order_id=order.id, user_id=order.user_id, status="open")
    disputes = FakeDisputeRepository([dispute])

    result = UpdateDisputeStatusUseCase(disputes).execute(
        dispute_id=dispute.id,
        new_status="under_review",
        resolution_notes="",
    )

    assert result.status == "under_review"


def test_update_dispute_not_found():
    """Updating a non-existent dispute raises DisputeNotFoundError."""
    disputes = FakeDisputeRepository([])

    with pytest.raises(DisputeNotFoundError):
        UpdateDisputeStatusUseCase(disputes).execute(
            dispute_id=uuid.uuid4(),
            new_status="resolved",
            resolution_notes="done",
        )
