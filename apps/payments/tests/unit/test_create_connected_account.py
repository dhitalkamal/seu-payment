"""Unit tests for CreateConnectedAccountUseCase."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from apps.payments.application.use_cases.create_connected_account import (
    CreateConnectedAccountUseCase,
)
from apps.payments.domain.entities import ConnectedAccountEntity
from apps.payments.domain.exceptions import ConnectedAccountNotFoundError, PayoutError
from apps.payments.domain.repositories import IConnectedAccountRepository


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


class FakeStripeConnectGateway:
    def create_account(self, org_id: uuid.UUID) -> str:
        return f"acct_fake_{org_id.hex[:8]}"

    def create_account_link(self, stripe_account_id: str, return_url: str, refresh_url: str) -> str:
        return f"https://connect.stripe.com/setup/fake/{stripe_account_id}"

    def transfer(self, *, stripe_account_id: str, amount: object, currency: str, description: str) -> str:
        return f"tr_fake_{stripe_account_id[:8]}"


class AlwaysFailStripeGateway:
    def create_account(self, org_id: uuid.UUID) -> str:
        raise PayoutError("Stripe unavailable.")

    def create_account_link(self, stripe_account_id: str, return_url: str, refresh_url: str) -> str:
        raise PayoutError("Stripe unavailable.")

    def transfer(self, *, stripe_account_id: str, amount: object, currency: str, description: str) -> str:
        raise PayoutError("Stripe unavailable.")


def test_create_connected_account_returns_entity() -> None:
    """CreateConnectedAccountUseCase stores a new entity and returns it."""
    repo = FakeConnectedAccountRepo()
    gw = FakeStripeConnectGateway()
    org_id = uuid.uuid4()

    result = CreateConnectedAccountUseCase(repo, gw).execute(
        org_id=org_id,
        return_url="https://example.com/return",
        refresh_url="https://example.com/refresh",
    )

    assert result.org_id == org_id
    assert result.stripe_account_id.startswith("acct_fake_")
    assert result.onboarding_url.startswith("https://connect.stripe.com")


def test_create_connected_account_persists() -> None:
    """Entity is retrievable from the repo after creation."""
    repo = FakeConnectedAccountRepo()
    gw = FakeStripeConnectGateway()
    org_id = uuid.uuid4()

    result = CreateConnectedAccountUseCase(repo, gw).execute(
        org_id=org_id,
        return_url="https://example.com/return",
        refresh_url="https://example.com/refresh",
    )

    fetched = repo.get_by_org(org_id)
    assert fetched is not None
    assert fetched.id == result.id


def test_create_connected_account_raises_on_stripe_error() -> None:
    """PayoutError propagates when the gateway fails."""
    repo = FakeConnectedAccountRepo()
    gw = AlwaysFailStripeGateway()

    with pytest.raises(PayoutError):
        CreateConnectedAccountUseCase(repo, gw).execute(
            org_id=uuid.uuid4(),
            return_url="https://example.com/return",
            refresh_url="https://example.com/refresh",
        )
