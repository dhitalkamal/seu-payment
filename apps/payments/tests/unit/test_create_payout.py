"""Unit tests for CreatePayoutUseCase."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from apps.payments.application.use_cases.create_payout import CreatePayoutUseCase
from apps.payments.domain.entities import ConnectedAccountEntity, PayoutEntity
from apps.payments.domain.exceptions import ConnectedAccountNotFoundError, PayoutError
from apps.payments.domain.repositories import IConnectedAccountRepository, IPayoutRepository


def _now() -> datetime:
    return datetime.now(timezone.utc)


class FakeConnectedAccountRepo(IConnectedAccountRepository):
    def __init__(self) -> None:
        self._store: dict[uuid.UUID, ConnectedAccountEntity] = {}

    def create(self, entity: ConnectedAccountEntity) -> ConnectedAccountEntity:
        self._store[entity.id] = entity
        return entity

    def get_by_org(self, org_id: uuid.UUID) -> ConnectedAccountEntity | None:
        return next((a for a in self._store.values() if a.org_id == org_id), None)

    def get_by_id(self, account_id: uuid.UUID) -> ConnectedAccountEntity:
        entity = self._store.get(account_id)
        if entity is None:
            raise ConnectedAccountNotFoundError("Connected account not found.")
        return entity


class FakePayoutRepo(IPayoutRepository):
    def __init__(self) -> None:
        self._store: dict[uuid.UUID, PayoutEntity] = {}

    def create(self, entity: PayoutEntity) -> PayoutEntity:
        self._store[entity.id] = entity
        return entity

    def list_by_org(self, org_id: uuid.UUID) -> list[PayoutEntity]:
        return [p for p in self._store.values() if p.org_id == org_id]


class FakeStripeConnectGateway:
    def create_account(self, org_id: uuid.UUID) -> str:
        return f"acct_fake_{org_id.hex[:8]}"

    def create_account_link(self, stripe_account_id: str, return_url: str, refresh_url: str) -> str:
        return f"https://connect.stripe.com/setup/fake/{stripe_account_id}"

    def transfer(self, *, stripe_account_id: str, amount: Decimal, currency: str, description: str) -> str:
        return f"tr_fake_{stripe_account_id[:8]}"


class AlwaysFailStripeGateway:
    def create_account(self, org_id: uuid.UUID) -> str:
        raise PayoutError("Stripe unavailable.")

    def create_account_link(self, stripe_account_id: str, return_url: str, refresh_url: str) -> str:
        raise PayoutError("Stripe unavailable.")

    def transfer(self, *, stripe_account_id: str, amount: Decimal, currency: str, description: str) -> str:
        raise PayoutError("Stripe unavailable.")


def test_create_payout_returns_entity() -> None:
    """CreatePayoutUseCase transfers funds and persists a payout record."""
    account_repo = FakeConnectedAccountRepo()
    payout_repo = FakePayoutRepo()
    gw = FakeStripeConnectGateway()
    org_id = uuid.uuid4()

    account = ConnectedAccountEntity(
        id=uuid.uuid4(),
        org_id=org_id,
        stripe_account_id="acct_test_123",
        onboarding_url="https://connect.stripe.com/setup/fake/acct_test_123",
        is_active=True,
        created_at=_now(),
    )
    account_repo.create(account)

    result = CreatePayoutUseCase(account_repo, payout_repo, gw).execute(
        org_id=org_id,
        amount=Decimal("500.00"),
        currency="USD",
        description="Event ticket proceeds",
    )

    assert result.org_id == org_id
    assert result.amount == Decimal("500.00")
    assert result.stripe_transfer_id.startswith("tr_fake_")


def test_create_payout_raises_when_no_connected_account() -> None:
    """ConnectedAccountNotFoundError raised when org has no connected account."""
    account_repo = FakeConnectedAccountRepo()
    payout_repo = FakePayoutRepo()
    gw = FakeStripeConnectGateway()

    with pytest.raises(ConnectedAccountNotFoundError):
        CreatePayoutUseCase(account_repo, payout_repo, gw).execute(
            org_id=uuid.uuid4(),
            amount=Decimal("500.00"),
            currency="USD",
            description="Event ticket proceeds",
        )


def test_create_payout_raises_on_transfer_failure() -> None:
    """PayoutError propagates when the Stripe transfer fails."""
    account_repo = FakeConnectedAccountRepo()
    payout_repo = FakePayoutRepo()
    gw = AlwaysFailStripeGateway()
    org_id = uuid.uuid4()

    account = ConnectedAccountEntity(
        id=uuid.uuid4(),
        org_id=org_id,
        stripe_account_id="acct_test_123",
        onboarding_url="https://connect.stripe.com/setup/fake/acct_test_123",
        is_active=True,
        created_at=_now(),
    )
    account_repo.create(account)

    with pytest.raises(PayoutError):
        CreatePayoutUseCase(account_repo, payout_repo, gw).execute(
            org_id=org_id,
            amount=Decimal("500.00"),
            currency="USD",
            description="Event ticket proceeds",
        )
