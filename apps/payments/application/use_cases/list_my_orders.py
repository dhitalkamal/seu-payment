"""Use case: list all payment orders belonging to the authenticated user."""

from __future__ import annotations

import uuid

from apps.payments.domain.entities import PaymentOrderEntity
from apps.payments.domain.repositories import IPaymentOrderRepository


class ListMyOrdersUseCase:
    """Return all orders owned by a given user."""

    def __init__(self, order_repo: IPaymentOrderRepository) -> None:
        self._orders = order_repo

    def execute(self, *, user_id: uuid.UUID) -> list[PaymentOrderEntity]:
        """Return all orders for user_id, newest first."""
        return self._orders.list_by_user(user_id)
