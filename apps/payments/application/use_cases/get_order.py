"""Use case: retrieve a single payment order owned by the requesting user."""

from __future__ import annotations

import uuid

from apps.payments.domain.entities import PaymentOrderEntity
from apps.payments.domain.repositories import IPaymentOrderRepository


class GetOrderUseCase:
    """Fetch a payment order, enforcing ownership."""

    def __init__(self, order_repo: IPaymentOrderRepository) -> None:
        self._orders = order_repo

    def execute(self, *, order_id: uuid.UUID, user_id: uuid.UUID) -> PaymentOrderEntity:
        """
        Return the order if it exists and belongs to user_id.

        @param order_id - UUID of the order to fetch
        @param user_id - UUID from JWT; must match order.user_id
        @raises OrderNotFoundError if absent or not owned by the user
        """
        return self._orders.get_by_id(order_id, user_id)
