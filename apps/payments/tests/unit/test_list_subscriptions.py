"""Tests for listing all subscriptions."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from apps.payments.domain.entities import SubscriptionEntity
from apps.payments.domain.repositories import ISubscriptionRepository


def _now() -> datetime:
    return datetime.now(timezone.utc)


def make_sub(**kwargs: object) -> SubscriptionEntity:
    """Build a SubscriptionEntity with sensible defaults."""
    now = _now()
    defaults: dict = {
        "id": uuid.uuid4(),
        "org_id": uuid.uuid4(),
        "plan": "starter",
        "status": "active",
        "gateway": "khalti",
        "gateway_subscription_id": "",
        "amount": Decimal("999.00"),
        "currency": "NPR",
        "current_period_start": now,
        "current_period_end": now,
        "created_at": now,
        "updated_at": now,
        "cancelled_at": None,
    }
    defaults.update(kwargs)
    return SubscriptionEntity(**defaults)  # type: ignore[arg-type]


class FakeSubscriptionRepository(ISubscriptionRepository):
    """Minimal in-memory subscription store for list_all tests."""

    def __init__(self, subs: list[SubscriptionEntity] | None = None) -> None:
        self._store: dict[uuid.UUID, SubscriptionEntity] = {
            s.id: s for s in (subs or [])
        }

    def create(self, entity: SubscriptionEntity) -> SubscriptionEntity:
        self._store[entity.id] = entity
        return entity

    def get_by_id(self, sub_id: uuid.UUID) -> SubscriptionEntity:
        return self._store[sub_id]

    def get_active_by_org(self, org_id: uuid.UUID) -> SubscriptionEntity | None:
        return next((s for s in self._store.values() if s.org_id == org_id and s.status == "active"), None)

    def get_by_gateway_id(self, gateway_subscription_id: str) -> SubscriptionEntity | None:
        return next((s for s in self._store.values() if s.gateway_subscription_id == gateway_subscription_id), None)

    def update(self, entity: SubscriptionEntity) -> SubscriptionEntity:
        self._store[entity.id] = entity
        return entity

    def list_by_org(self, org_id: uuid.UUID) -> list[SubscriptionEntity]:
        return [s for s in self._store.values() if s.org_id == org_id]

    def list_all(self) -> list[SubscriptionEntity]:
        return list(self._store.values())


def test_list_all_returns_empty_when_no_subscriptions() -> None:
    repo = FakeSubscriptionRepository()
    assert repo.list_all() == []


def test_list_all_returns_all_subscriptions() -> None:
    sub_a = make_sub()
    sub_b = make_sub()
    repo = FakeSubscriptionRepository([sub_a, sub_b])
    result = repo.list_all()
    assert len(result) == 2
    assert {s.id for s in result} == {sub_a.id, sub_b.id}


def test_list_all_returns_subscriptions_across_multiple_orgs() -> None:
    org_x = uuid.uuid4()
    org_y = uuid.uuid4()
    sub_x = make_sub(org_id=org_x)
    sub_y = make_sub(org_id=org_y)
    repo = FakeSubscriptionRepository([sub_x, sub_y])
    result = repo.list_all()
    org_ids = {s.org_id for s in result}
    assert org_x in org_ids
    assert org_y in org_ids
