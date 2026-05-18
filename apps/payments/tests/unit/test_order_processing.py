"""Unit tests for the order processing status transition."""

from __future__ import annotations

import uuid
from decimal import Decimal

from apps.payments.application.use_cases.create_order import CreatePaymentOrderUseCase
from apps.payments.application.use_cases.process_to_processing import TransitionToProcessingUseCase
from apps.payments.tests.unit.fakes import FakePaymentOrderRepository, FakePromoCodeRepository


def _make_order_via_use_case(order_repo: FakePaymentOrderRepository) -> str:
    """Create an order and return its ID."""
    result = CreatePaymentOrderUseCase(
        order_repo=order_repo,
        promo_repo=FakePromoCodeRepository(None),
    ).execute(
        user_id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        registration_id=uuid.uuid4(),
        subtotal=Decimal("1000.00"),
        gateway="khalti",
        idempotency_key=uuid.uuid4(),
        promo_code=None,
    )
    return str(result.id)


def test_transition_to_processing_updates_status():
    """TransitionToProcessingUseCase sets order status to processing."""
    repo = FakePaymentOrderRepository()
    order_id = _make_order_via_use_case(repo)
    result = TransitionToProcessingUseCase(repo).execute(order_id=uuid.UUID(order_id))
    assert result.status == "processing"


def test_new_order_starts_as_created():
    """Orders start with status=created before gateway redirect."""
    repo = FakePaymentOrderRepository()
    order_id = _make_order_via_use_case(repo)
    order = repo._store[uuid.UUID(order_id)]
    assert order.status == "created"
