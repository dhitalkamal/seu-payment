"""Use case: open a new dispute against a completed payment order."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from apps.payments.domain.entities import DisputeEntity
from apps.payments.domain.repositories import IDisputeRepository, IPaymentOrderRepository


class CreateDisputeUseCase:
    """Validate order ownership and create a new dispute record."""

    def __init__(
        self,
        order_repo: IPaymentOrderRepository,
        dispute_repo: IDisputeRepository,
    ) -> None:
        self._orders = order_repo
        self._disputes = dispute_repo

    def execute(
        self,
        *,
        order_id: uuid.UUID,
        user_id: uuid.UUID,
        reason: str,
        description: str,
        evidence: dict | None = None,
    ) -> DisputeEntity:
        """Create and persist a dispute, returning the new entity."""
        # Ownership check - raises OrderNotFoundError if order not found or not owned
        self._orders.get_by_id(order_id, user_id)
        now = datetime.now(timezone.utc)
        dispute = DisputeEntity(
            id=uuid.uuid4(),
            order_id=order_id,
            user_id=user_id,
            status="open",
            reason=reason,
            description=description,
            evidence=evidence or {},
            gateway_dispute_id="",
            resolved_at=None,
            created_at=now,
            updated_at=now,
        )
        return self._disputes.create(dispute)
