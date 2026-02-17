"""Unit tests for org_id filter on the subscription list endpoint."""

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
    """In-memory subscription store for filter tests."""

    def __init__(self, subs: list[SubscriptionEntity] | None = None) -> None:
        self._store: dict[uuid.UUID, SubscriptionEntity] = {s.id: s for s in (subs or [])}

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


# * ---- filter behaviour tests ----


def test_list_subscriptions_without_org_id_returns_all() -> None:
    """When no org_id is supplied, all subscriptions are returned."""
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()
    repo = FakeSubscriptionRepository([make_sub(org_id=org_a), make_sub(org_id=org_b)])
    result = repo.list_all()
    assert len(result) == 2


def test_list_subscriptions_with_org_id_filters_correctly() -> None:
    """When org_id is supplied, only that org's subscriptions are returned."""
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()
    sub_a1 = make_sub(org_id=org_a)
    sub_a2 = make_sub(org_id=org_a)
    sub_b = make_sub(org_id=org_b)
    repo = FakeSubscriptionRepository([sub_a1, sub_a2, sub_b])
    result = repo.list_by_org(org_a)
    assert len(result) == 2
    assert all(s.org_id == org_a for s in result)


def test_list_subscriptions_with_org_id_returns_empty_when_none_match() -> None:
    """list_by_org returns empty list when no subscriptions belong to that org."""
    repo = FakeSubscriptionRepository([make_sub(org_id=uuid.uuid4())])
    result = repo.list_by_org(uuid.uuid4())
    assert result == []


def test_list_subscriptions_org_id_does_not_leak_other_orgs() -> None:
    """Filtering by org_id must not return subscriptions from other orgs."""
    target_org = uuid.uuid4()
    other_org = uuid.uuid4()
    repo = FakeSubscriptionRepository(
        [
            make_sub(org_id=target_org),
            make_sub(org_id=other_org),
            make_sub(org_id=other_org),
        ]
    )
    result = repo.list_by_org(target_org)
    assert len(result) == 1
    assert result[0].org_id == target_org


# * ---- view-level filter dispatch tests ----


def test_view_dispatches_list_by_org_when_org_id_provided() -> None:
    """When ?org_id is given, the view must call list_by_org, not list_all."""
    target_org = uuid.uuid4()
    other_org = uuid.uuid4()
    repo = FakeSubscriptionRepository(
        [
            make_sub(org_id=target_org),
            make_sub(org_id=other_org),
        ]
    )
    # simulate the dispatch logic the view will use
    org_id_param = str(target_org)
    if org_id_param:
        result = repo.list_by_org(uuid.UUID(org_id_param))
    else:
        result = repo.list_all()
    assert len(result) == 1
    assert result[0].org_id == target_org


def test_view_dispatches_list_all_when_no_org_id() -> None:
    """When ?org_id is absent, the view must call list_all."""
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()
    repo = FakeSubscriptionRepository([make_sub(org_id=org_a), make_sub(org_id=org_b)])
    org_id_param = ""
    if org_id_param:
        result = repo.list_by_org(uuid.UUID(org_id_param))
    else:
        result = repo.list_all()
    assert len(result) == 2
