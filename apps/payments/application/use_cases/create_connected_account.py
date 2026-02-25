"""Use case: register a Stripe Connect account for an organizer."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from apps.payments.domain.entities import ConnectedAccountEntity
from apps.payments.domain.repositories import IConnectedAccountRepository


class CreateConnectedAccountUseCase:
    """Create a Stripe Connect account and generate an onboarding link."""

    def __init__(self, repo: IConnectedAccountRepository, gateway: object) -> None:
        self._repo = repo
        self._gateway = gateway

    def execute(self, *, org_id: uuid.UUID, return_url: str, refresh_url: str) -> ConnectedAccountEntity:
        """Create the Stripe account, build the onboarding URL, and persist the entity."""
        stripe_account_id: str = self._gateway.create_account(org_id)
        onboarding_url: str = self._gateway.create_account_link(stripe_account_id, return_url, refresh_url)

        entity = ConnectedAccountEntity(
            id=uuid.uuid4(),
            org_id=org_id,
            stripe_account_id=stripe_account_id,
            onboarding_url=onboarding_url,
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        return self._repo.create(entity)
