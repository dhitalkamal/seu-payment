"""Use case: process a subscription payment webhook and activate/extend the plan."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from apps.payments.domain.entities import SubscriptionEntity, SubscriptionPaymentEntity
from apps.payments.domain.repositories import ISubscriptionPaymentRepository, ISubscriptionRepository
from apps.payments.infrastructure.publisher import publish_event

# ! billing period is 30 days
BILLING_PERIOD_DAYS = 30


class ProcessSubscriptionWebhookUseCase:
    """Handle a successful subscription payment — record it and notify management service."""

    def __init__(
        self,
        sub_repo: ISubscriptionRepository,
        payment_repo: ISubscriptionPaymentRepository,
    ) -> None:
        self._subs = sub_repo
        self._payments = payment_repo

    def execute(
        self,
        *,
        gateway_subscription_id: str,
        gateway_transaction_id: str,
        amount: Decimal,
        currency: str = "NPR",
        status: str = "completed",
    ) -> SubscriptionEntity | None:
        """
        Record the payment and extend the subscription period.

        Called by the Stripe/PayPal/Khalti webhook handlers when a subscription
        payment succeeds. The subscription's period is extended by 30 days and
        a subscription.activated event is published.

        @param gateway_subscription_id - matches subscription.gateway_subscription_id
        @param gateway_transaction_id - the gateway's unique transaction ID
        @param amount - payment amount
        @param currency - currency code
        @param status - completed | failed
        @returns the updated subscription, or None if not found
        """
        sub = self._subs.get_by_gateway_id(gateway_subscription_id)
        if sub is None:
            return None

        now = datetime.now(timezone.utc)
        period_end = now + timedelta(days=BILLING_PERIOD_DAYS)

        if status == "completed":
            # * record the payment
            payment = SubscriptionPaymentEntity(
                id=uuid.uuid4(),
                subscription_id=sub.id,
                amount=amount,
                currency=currency,
                status="completed",
                gateway_transaction_id=gateway_transaction_id,
                period_start=now,
                period_end=period_end,
                paid_at=now,
            )
            self._payments.create(payment)

            # * extend the subscription period
            sub.status = "active"
            sub.current_period_start = now
            sub.current_period_end = period_end
            sub = self._subs.update(sub)

            # * tell the management service to update the org's plan
            publish_event(
                routing_key="subscription.activated",
                payload={
                    "org_id": str(sub.org_id),
                    "plan": sub.plan,
                    "plan_expires_at": period_end.isoformat(),
                    "subscription_id": str(sub.id),
                },
            )
        elif status == "failed":
            sub.status = "past_due"
            sub = self._subs.update(sub)

        return sub
