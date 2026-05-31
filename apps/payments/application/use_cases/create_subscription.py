"""Use case: create an org subscription, call the gateway, return the payment URL."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from apps.payments.domain.entities import SubscriptionEntity
from apps.payments.domain.gateway import IPaymentGateway, PaymentSession
from apps.payments.domain.repositories import ISubscriptionRepository
from apps.payments.infrastructure.publisher import publish_event

# ! plan prices in NPR - must stay in sync with PLAN_CATALOGUE on the frontend
PLAN_PRICES: dict[str, Decimal] = {
    "free": Decimal("0.00"),
    "starter": Decimal("999.00"),
    "pro": Decimal("4999.00"),
    "ngo": Decimal("0.00"),
    "enterprise": Decimal("14999.00"),
}

# ! billing period is 30 days for all plans
BILLING_PERIOD_DAYS = 30


class CreateSubscriptionUseCase:
    """Subscribe an org to a paid plan via the chosen payment gateway."""

    def __init__(
        self,
        sub_repo: ISubscriptionRepository,
        gateway_client: IPaymentGateway | None = None,
    ) -> None:
        self._subs = sub_repo
        self._gateway = gateway_client

    def execute(
        self,
        *,
        org_id: uuid.UUID,
        plan: str,
        gateway: str,
        return_url: str = "",
        cancel_url: str = "",
        customer_email: str = "",
    ) -> tuple[SubscriptionEntity, PaymentSession | None]:
        """Create a subscription. Free plans activate immediately. Paid plans call gateway first."""
        if plan not in PLAN_PRICES:
            raise ValueError(f"Invalid subscription plan: {plan}")

        now = datetime.now(timezone.utc)
        amount = PLAN_PRICES[plan]
        existing = self._subs.get_active_by_org(org_id)

        # downgrade to free - just cancel existing, no new subscription needed
        if plan == "free":
            if existing is not None:
                existing.status = "cancelled"
                existing.cancelled_at = now
                self._subs.update(existing)
                publish_event(
                    routing_key="subscription.cancelled",
                    payload={"org_id": str(org_id), "plan": existing.plan, "subscription_id": str(existing.id)},
                )
            free_sub = SubscriptionEntity(
                id=uuid.uuid4(),
                org_id=org_id,
                plan="free",
                status="active",
                gateway="none",
                gateway_subscription_id="",
                amount=Decimal("0.00"),
                currency="NPR",
                current_period_start=now,
                current_period_end=now + timedelta(days=36500),
                created_at=now,
                updated_at=now,
            )
            return free_sub, None

        # free plans (ngo) - activate immediately
        if amount == Decimal("0.00"):
            if existing is not None:
                existing.status = "cancelled"
                existing.cancelled_at = now
                self._subs.update(existing)

            period_end = now + timedelta(days=BILLING_PERIOD_DAYS)
            sub = SubscriptionEntity(
                id=uuid.uuid4(),
                org_id=org_id,
                plan=plan,
                status="active",
                gateway="none",
                gateway_subscription_id="",
                amount=amount,
                currency="NPR",
                current_period_start=now,
                current_period_end=period_end,
                created_at=now,
                updated_at=now,
            )
            sub = self._subs.create(sub)
            publish_event(
                routing_key="subscription.activated",
                payload={
                    "org_id": str(org_id),
                    "plan": plan,
                    "plan_expires_at": period_end.isoformat(),
                    "subscription_id": str(sub.id),
                },
            )
            return sub, None

        # paid plan - call gateway FIRST, save subscription only on success
        if self._gateway is None:
            raise ValueError("Payment gateway required for paid plans")

        period_end = now + timedelta(days=BILLING_PERIOD_DAYS)
        sub_id = uuid.uuid4()

        # this raises PaymentGatewayError if it fails - subscription is NOT saved
        session = self._gateway.initiate(
            order_id=str(sub_id),
            amount=amount,
            currency="NPR",
            description=f"Sansaar {plan.title()} Plan - Monthly",
            customer_email=customer_email,
            return_url=return_url,
            cancel_url=cancel_url,
        )

        # gateway succeeded - cancel existing, save new as pending
        if existing is not None:
            existing.status = "cancelled"
            existing.cancelled_at = now
            self._subs.update(existing)
            publish_event(
                routing_key="subscription.cancelled",
                payload={"org_id": str(org_id), "plan": existing.plan, "subscription_id": str(existing.id)},
            )

        sub = SubscriptionEntity(
            id=sub_id,
            org_id=org_id,
            plan=plan,
            status="pending",
            gateway=gateway,
            gateway_subscription_id=session.gateway_order_id,
            amount=amount,
            currency="NPR",
            current_period_start=now,
            current_period_end=period_end,
            created_at=now,
            updated_at=now,
        )
        sub = self._subs.create(sub)
        return sub, session
