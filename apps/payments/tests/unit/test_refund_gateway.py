"""Unit tests for refund gateway execution in RequestRefundUseCase."""

from __future__ import annotations

import uuid
from decimal import Decimal

from apps.payments.application.use_cases.request_refund import RequestRefundUseCase
from apps.payments.domain.exceptions import PaymentGatewayError
from apps.payments.domain.gateway import IPaymentGateway, PaymentSession
from apps.payments.tests.unit.fakes import (
    FakePaymentOrderRepository,
    FakeRefundRepository,
    make_order,
)


class FakeGatewaySuccess(IPaymentGateway):
    """Gateway that always succeeds and records calls."""

    def __init__(self, gateway_refund_id: str = "ref_123") -> None:
        self.refund_calls: list[dict] = []
        self._gateway_refund_id = gateway_refund_id

    def initiate(self, **kwargs: object) -> PaymentSession:
        """Not used in refund tests."""
        raise NotImplementedError

    def refund(self, *, gateway_order_id: str, amount: Decimal) -> str:
        """Record the call and return a fake refund ID."""
        self.refund_calls.append({"gateway_order_id": gateway_order_id, "amount": amount})
        return self._gateway_refund_id


class FakeGatewayFailure(IPaymentGateway):
    """Gateway that always raises PaymentGatewayError on refund."""

    def initiate(self, **kwargs: object) -> PaymentSession:
        """Not used in refund tests."""
        raise NotImplementedError

    def refund(self, *, gateway_order_id: str, amount: Decimal) -> str:
        """Always fail."""
        raise PaymentGatewayError("Gateway rejected the refund.")


def _uc(orders=None, gateway=None) -> RequestRefundUseCase:
    return RequestRefundUseCase(
        order_repo=FakePaymentOrderRepository(orders or []),
        refund_repo=FakeRefundRepository(),
        gateway=gateway or FakeGatewaySuccess(),
    )


def test_refund_gateway_called_with_correct_args():
    """Gateway refund is called with the order's gateway_order_id and amount."""
    user_id = uuid.uuid4()
    order = make_order(user_id=user_id, status="completed", gateway_order_id="sess_abc")
    gw = FakeGatewaySuccess()

    _uc(orders=[order], gateway=gw).execute(
        order_id=order.id,
        user_id=user_id,
        reason="Test",
        amount=Decimal("500.00"),
    )

    assert len(gw.refund_calls) == 1
    assert gw.refund_calls[0]["gateway_order_id"] == "sess_abc"
    assert gw.refund_calls[0]["amount"] == Decimal("500.00")


def test_refund_status_completed_on_gateway_success():
    """Refund entity has status=completed after a successful gateway call."""
    user_id = uuid.uuid4()
    order = make_order(user_id=user_id, status="completed", gateway_order_id="sess_abc")

    result = _uc(orders=[order]).execute(order_id=order.id, user_id=user_id, reason="Test")

    assert result.status == "completed"


def test_refund_gateway_refund_id_stored():
    """gateway_refund_id from gateway response is persisted on the RefundEntity."""
    user_id = uuid.uuid4()
    order = make_order(user_id=user_id, status="completed", gateway_order_id="sess_abc")
    gw = FakeGatewaySuccess(gateway_refund_id="re_xyz")

    result = _uc(orders=[order], gateway=gw).execute(order_id=order.id, user_id=user_id, reason="Test")

    assert result.gateway_refund_id == "re_xyz"


def test_refund_status_failed_on_gateway_error():
    """Refund entity has status=failed when the gateway raises."""
    user_id = uuid.uuid4()
    order = make_order(user_id=user_id, status="completed", gateway_order_id="sess_abc")
    refund_repo = FakeRefundRepository()

    RequestRefundUseCase(
        order_repo=FakePaymentOrderRepository([order]),
        refund_repo=refund_repo,
        gateway=FakeGatewayFailure(),
    ).execute(order_id=order.id, user_id=user_id, reason="Test")

    stored = list(refund_repo._store.values())[0]
    assert stored.status == "failed"


def test_refund_error_message_stored_on_failure():
    """Error message from gateway is stored in the refund's gateway_refund_id field."""
    user_id = uuid.uuid4()
    order = make_order(user_id=user_id, status="completed", gateway_order_id="sess_abc")
    refund_repo = FakeRefundRepository()

    RequestRefundUseCase(
        order_repo=FakePaymentOrderRepository([order]),
        refund_repo=refund_repo,
        gateway=FakeGatewayFailure(),
    ).execute(order_id=order.id, user_id=user_id, reason="Test")

    stored = list(refund_repo._store.values())[0]
    assert "Gateway rejected" in stored.gateway_refund_id
