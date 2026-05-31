"""Use case: transition a newly-created order to processing status."""

from __future__ import annotations

import uuid

from apps.payments.domain.entities import PaymentOrderEntity
from apps.payments.domain.repositories import IPaymentOrderRepository


class TransitionToProcessingUseCase:
    """Move an order from created to processing when the user is redirected to the gateway."""

    def __init__(self, order_repo: IPaymentOrderRepository) -> None:
        self._orders = order_repo

    def execute(self, *, order_id: uuid.UUID) -> PaymentOrderEntity:
        """
        Set order status to processing.

        @param order_id - the order to update
        @raises OrderNotFoundError if the order does not exist
        """
        order = self._orders.get_by_order_id(order_id)
        order.status = "processing"
        return self._orders.update(order)
