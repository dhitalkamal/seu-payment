"""Use case: request a refund on a completed payment order."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from apps.payments.domain.entities import RefundEntity
from apps.payments.domain.exceptions import RefundNotAllowedError
from apps.payments.domain.repositories import IPaymentOrderRepository, IRefundRepository


class RequestRefundUseCase:
    """Create a PENDING refund and mark the order as REFUNDED."""

    def __init__(
        self,
        order_repo: IPaymentOrderRepository,
        refund_repo: IRefundRepository,
    ) -> None:
        self._orders = order_repo
        self._refunds = refund_repo

    def execute(
        self,
        *,
        order_id: uuid.UUID,
        user_id: uuid.UUID,
        reason: str,
        amount: Decimal | None = None,
    ) -> RefundEntity:
        """
        Validate order ownership and status, then create a pending refund.

        @param order_id - the order to refund
        @param user_id - UUID from JWT; must own the order
        @param reason - required explanation for the refund
        @param amount - refund amount; defaults to order total_amount if None
        @returns the created RefundEntity with status=pending
        @raises OrderNotFoundError if order is missing or not owned by user
        @raises RefundNotAllowedError if the order is not in completed status
        """
        order = self._orders.get_by_id(order_id, user_id)

        if order.status != "completed":
            raise RefundNotAllowedError(f"Cannot refund an order with status '{order.status}'.")

        refund_amount = amount if amount is not None else order.total_amount

        now = datetime.now(timezone.utc)
        refund = RefundEntity(
            id=uuid.uuid4(),
            order_id=order.id,
            amount=refund_amount,
            reason=reason,
            status="pending",
            gateway_refund_id="",
            created_at=now,
        )

        order.status = "refunded"
        order.updated_at = now
        self._orders.update(order)

        return self._refunds.create(refund)
