"""Use case: list disputes for a given order."""

from __future__ import annotations

import uuid

from apps.payments.domain.entities import DisputeEntity
from apps.payments.domain.repositories import IDisputeRepository


class ListDisputesUseCase:
    """Return all disputes belonging to a specific order and user."""

    def __init__(self, dispute_repo: IDisputeRepository) -> None:
        self._disputes = dispute_repo

    def execute(self, *, order_id: uuid.UUID, user_id: uuid.UUID) -> list[DisputeEntity]:
        """Return disputes scoped to the given order and user."""
        return self._disputes.list_by_order(order_id=order_id, user_id=user_id)
