"""Use case: cancel an active subscription and revert the org to the free plan."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from apps.payments.domain.entities import SubscriptionEntity
from apps.payments.domain.exceptions import SubscriptionNotFoundError
from apps.payments.domain.repositories import ISubscriptionRepository
from apps.payments.infrastructure.publisher import publish_event


class CancelSubscriptionUseCase:
    """Cancel the org's active subscription — plan reverts to free at period end."""

    def __init__(self, sub_repo: ISubscriptionRepository) -> None:
        self._subs = sub_repo

    def execute(self, *, org_id: uuid.UUID) -> SubscriptionEntity:
        """
        Mark the org's active subscription as cancelled.

        The org keeps their plan features until current_period_end, then the
        management service consumer will revert them to free.

        @param org_id - UUID of the organisation
        @raises SubscriptionNotFoundError if no active subscription exists
        """
        sub = self._subs.get_active_by_org(org_id)
        if sub is None:
            raise SubscriptionNotFoundError("No active subscription found for this organisation.")

        sub.status = "cancelled"
        sub.cancelled_at = datetime.now(timezone.utc)
        sub = self._subs.update(sub)

        # * notify management service to schedule plan revert at period end
        publish_event(
            routing_key="subscription.cancelled",
            payload={
                "org_id": str(org_id),
                "subscription_id": str(sub.id),
                "plan": sub.plan,
                "effective_at": sub.current_period_end.isoformat(),
            },
        )

        return sub
