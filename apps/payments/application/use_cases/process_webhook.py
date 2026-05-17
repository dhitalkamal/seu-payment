"""Use case: process a payment gateway webhook callback."""

from __future__ import annotations

from datetime import datetime, timezone

from apps.payments.domain.entities import PaymentOrderEntity
from apps.payments.domain.exceptions import OrderNotFoundError
from apps.payments.domain.repositories import IPaymentOrderRepository

# ! terminal statuses — no further transitions allowed
_TERMINAL_STATUSES: frozenset[str] = frozenset({"completed", "failed", "cancelled"})


class ProcessWebhookUseCase:
    """Update an order's status based on a provider webhook callback."""

    def __init__(self, order_repo: IPaymentOrderRepository) -> None:
        self._orders = order_repo

    def execute(
        self,
        *,
        gateway_order_id: str,
        status: str,
        gateway_transaction_id: str,
    ) -> PaymentOrderEntity:
        """
        Locate the order by gateway_order_id and apply the status update.

        @param gateway_order_id - provider-issued order ID stored on creation
        @param status - completed | failed (from the provider callback)
        @param gateway_transaction_id - provider transaction ID for reconciliation
        @raises OrderNotFoundError if no order matches the gateway_order_id
        """
        order = self._orders.get_by_gateway_order_id(gateway_order_id)
        if order is None:
            raise OrderNotFoundError("No order found for this gateway_order_id.")

        # * idempotency — skip if already in a terminal state
        if order.status in _TERMINAL_STATUSES:
            return order

        order.status = status
        if status == "completed":
            order.completed_at = datetime.now(timezone.utc)

        return self._orders.update(order)
