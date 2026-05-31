"""Use case: request a refund on a completed payment order."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from apps.payments.domain.entities import RefundEntity
from apps.payments.domain.exceptions import RefundNotAllowedError
from apps.payments.domain.gateway import IPaymentGateway
from apps.payments.domain.repositories import IPaymentOrderRepository, IRefundRepository


class RequestRefundUseCase:
    """Create a refund record and execute it via the payment gateway."""

    def __init__(
        self,
        order_repo: IPaymentOrderRepository,
        refund_repo: IRefundRepository,
        gateway: IPaymentGateway,
    ) -> None:
        self._orders = order_repo
        self._refunds = refund_repo
        self._gateway = gateway

    def execute(
        self,
        *,
        order_id: uuid.UUID,
        user_id: uuid.UUID,
        reason: str,
        amount: Decimal | None = None,
    ) -> RefundEntity:
        """
        Validate order ownership and status, create a refund record, then call the gateway.

        On gateway success the refund is marked completed with the provider refund ID.
        On gateway failure the refund is marked failed and the error message is stored;
        no exception is re-raised so the caller always gets a RefundEntity back.

        @param order_id - the order to refund
        @param user_id - UUID from JWT; must own the order
        @param reason - required explanation for the refund
        @param amount - refund amount; defaults to order total_amount if None
        @returns the created RefundEntity with status=completed or status=failed
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
        refund = self._refunds.create(refund)

        order.status = "refunded"
        order.updated_at = now
        self._orders.update(order)

        # * attempt gateway execution; record outcome without propagating the exception
        try:
            gateway_refund_id = self._gateway.refund(
                gateway_order_id=order.gateway_order_id,
                amount=refund_amount,
            )
            refund.status = "completed"
            refund.gateway_refund_id = gateway_refund_id
        except Exception as exc:
            refund.status = "failed"
            refund.gateway_refund_id = str(exc)

        return self._refunds.update(refund)
