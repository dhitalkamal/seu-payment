"""Use case: create an org subscription, call the gateway, return the payment URL."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from apps.payments.domain.entities import SubscriptionEntity
from apps.payments.domain.exceptions import ActiveSubscriptionExistsError
from apps.payments.domain.gateway import IPaymentGateway, PaymentSession
from apps.payments.domain.repositories import ISubscriptionRepository
from apps.payments.infrastructure.publisher import publish_event

# ! plan prices in NPR — must stay in sync with PLAN_CATALOGUE on the frontend
PLAN_PRICES: dict[str, Decimal] = {
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
        """
        Create a subscription record, call the gateway for payment, return the payment URL.

        For NGO plans (free), the subscription is activated immediately with no payment.
        For paid plans (starter/pro/enterprise), the gateway is called and the subscription
        stays in 'active' pending confirmation — the webhook will record the payment.

        @param org_id - UUID of the organization
        @param plan - one of starter, pro, ngo, enterprise
        @param gateway - khalti | esewa | stripe | paypal
        @param return_url - where the gateway redirects on success
        @param cancel_url - where the gateway redirects on failure
        @param customer_email - org admin email for gateway display
        @raises ActiveSubscriptionExistsError if the org already has an active subscription
        @raises ValueError if the plan name is invalid
        @raises PaymentGatewayError if the gateway rejects the request
        """
        if plan not in PLAN_PRICES:
            raise ValueError(f"Invalid subscription plan: {plan}")

        # ! block duplicate active subscriptions
        existing = self._subs.get_active_by_org(org_id)
        if existing is not None:
            raise ActiveSubscriptionExistsError("This organization already has an active subscription. Cancel it first.")

        now = datetime.now(timezone.utc)
        period_end = now + timedelta(days=BILLING_PERIOD_DAYS)
        amount = PLAN_PRICES[plan]

        sub = SubscriptionEntity(
            id=uuid.uuid4(),
            org_id=org_id,
            plan=plan,
            status="active",
            gateway=gateway,
            gateway_subscription_id="",
            amount=amount,
            currency="NPR",
            current_period_start=now,
            current_period_end=period_end,
            created_at=now,
            updated_at=now,
        )
        sub = self._subs.create(sub)

        # * NGO plan is free — activate immediately, no payment needed
        if amount == Decimal("0.00"):
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

        # * paid plan — call the gateway for payment
        session: PaymentSession | None = None
        if self._gateway is not None:
            session = self._gateway.initiate(
                order_id=str(sub.id),
                amount=amount,
                currency="NPR",
                description=f"Sansaar {plan.title()} Plan — Monthly",
                customer_email=customer_email,
                return_url=return_url,
                cancel_url=cancel_url,
            )
            sub.gateway_subscription_id = session.gateway_order_id
            sub = self._subs.update(sub)

        return sub, session
