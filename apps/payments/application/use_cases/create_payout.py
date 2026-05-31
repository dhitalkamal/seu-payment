"""Use case: transfer event proceeds to an organizer's connected Stripe account."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from apps.payments.domain.entities import PayoutEntity
from apps.payments.domain.exceptions import ConnectedAccountNotFoundError
from apps.payments.domain.repositories import IConnectedAccountRepository, IPayoutRepository


class CreatePayoutUseCase:
    """Transfer funds to an organizer's Stripe Connect account and record the payout."""

    def __init__(
        self,
        account_repo: IConnectedAccountRepository,
        payout_repo: IPayoutRepository,
        gateway: object,
    ) -> None:
        self._account_repo = account_repo
        self._payout_repo = payout_repo
        self._gateway = gateway

    def execute(
        self,
        *,
        org_id: uuid.UUID,
        amount: Decimal,
        currency: str,
        description: str,
    ) -> PayoutEntity:
        """Look up the connected account, run the Stripe transfer, and persist the payout."""
        account = self._account_repo.get_by_org(org_id)
        if account is None:
            raise ConnectedAccountNotFoundError("No connected account found for this org.")

        transfer_id: str = self._gateway.transfer(
            stripe_account_id=account.stripe_account_id,
            amount=amount,
            currency=currency,
            description=description,
        )

        entity = PayoutEntity(
            id=uuid.uuid4(),
            org_id=org_id,
            stripe_account_id=account.stripe_account_id,
            stripe_transfer_id=transfer_id,
            amount=amount,
            currency=currency,
            description=description,
            created_at=datetime.now(timezone.utc),
        )
        return self._payout_repo.create(entity)
