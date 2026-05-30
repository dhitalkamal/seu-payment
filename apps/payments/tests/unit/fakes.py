"""Hand-rolled in-memory fakes for all payment repository interfaces."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Sequence

from apps.payments.domain.entities import (
    DisputeEntity,
    PaymentOrderEntity,
    PromoCodeEntity,
    RefundEntity,
)
from apps.payments.domain.exceptions import (
    DisputeNotFoundError,
    InvalidPromoCodeError,
    OrderNotFoundError,
)
from apps.payments.domain.repositories import (
    IDisputeRepository,
    IPaymentOrderRepository,
    IPromoCodeRepository,
    IRefundRepository,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def make_order(**kwargs: object) -> PaymentOrderEntity:
    """Build a PaymentOrderEntity with sensible defaults for testing."""
    now = _now()
    defaults: dict = {
        "id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "event_id": uuid.uuid4(),
        "registration_id": uuid.uuid4(),
        "subtotal": Decimal("1000.00"),
        "discount_amount": Decimal("0.00"),
        "tax_amount": Decimal("0.00"),
        "gateway_fee": Decimal("0.00"),
        "platform_fee": Decimal("50.00"),
        "total_amount": Decimal("1050.00"),
        "currency": "NPR",
        "status": "created",
        "gateway": "khalti",
        "gateway_order_id": "",
        "idempotency_key": uuid.uuid4(),
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
    }
    defaults.update(kwargs)
    return PaymentOrderEntity(**defaults)  # type: ignore[arg-type]


def make_promo(**kwargs: object) -> PromoCodeEntity:
    """Build a PromoCodeEntity with sensible defaults for testing."""
    now = _now()
    defaults: dict = {
        "id": uuid.uuid4(),
        "code": "SAVE10",
        "discount_type": "percentage",
        "discount_value": Decimal("10"),
        "valid_from": now - timedelta(days=1),
        "valid_until": now + timedelta(days=30),
        "is_active": True,
        "max_usage_count": 100,
        "used_count": 0,
        "created_at": now,
    }
    defaults.update(kwargs)
    return PromoCodeEntity(**defaults)  # type: ignore[arg-type]


class FakePaymentOrderRepository(IPaymentOrderRepository):
    """In-memory payment order store."""

    def __init__(self, orders: Sequence[PaymentOrderEntity] | None = None) -> None:
        self._store: dict[uuid.UUID, PaymentOrderEntity] = {o.id: o for o in (orders or [])}

    def create(self, entity: PaymentOrderEntity) -> PaymentOrderEntity:
        """Persist and return the entity."""
        self._store[entity.id] = entity
        return entity

    def get_by_id(self, order_id: uuid.UUID, user_id: uuid.UUID) -> PaymentOrderEntity:
        """Raise OrderNotFoundError if absent or not owned by user."""
        entity = self._store.get(order_id)
        if entity is None or entity.user_id != user_id:
            raise OrderNotFoundError("Order not found.")
        return entity

    def get_by_idempotency_key(self, key: uuid.UUID) -> PaymentOrderEntity | None:
        """Return the order with this idempotency key, or None."""
        for order in self._store.values():
            if order.idempotency_key == key:
                return order
        return None

    def has_order_for_registration(self, registration_id: uuid.UUID) -> bool:
        """True if any order exists for this registration."""
        return any(o.registration_id == registration_id for o in self._store.values())

    def has_active_order_for_event(self, user_id: uuid.UUID, event_id: uuid.UUID) -> bool:
        """True if user has a non-failed order for this event."""
        return any(
            o.user_id == user_id and o.event_id == event_id and o.status not in ("failed", "refunded")
            for o in self._store.values()
        )

    def update(self, entity: PaymentOrderEntity) -> PaymentOrderEntity:
        """Overwrite the stored entity and return it."""
        self._store[entity.id] = entity
        return entity

    def list_by_user(self, user_id: uuid.UUID) -> list[PaymentOrderEntity]:
        """Return all orders owned by the given user."""
        return [o for o in self._store.values() if o.user_id == user_id]

    def get_by_order_id(self, order_id: uuid.UUID) -> PaymentOrderEntity:
        """Return the order by its own ID. Raises OrderNotFoundError if absent."""
        entity = self._store.get(order_id)
        if entity is None:
            raise OrderNotFoundError("Order not found.")
        return entity

    def get_by_gateway_order_id(self, gateway_order_id: str) -> PaymentOrderEntity | None:
        """Return the order with this gateway_order_id or None."""
        return next(
            (o for o in self._store.values() if o.gateway_order_id == gateway_order_id),
            None,
        )

    def list_all(self) -> list[PaymentOrderEntity]:
        """Return every stored order regardless of user."""
        return list(self._store.values())


class FakeRefundRepository(IRefundRepository):
    """In-memory refund store."""

    def __init__(self) -> None:
        self._store: dict[uuid.UUID, RefundEntity] = {}

    def create(self, entity: RefundEntity) -> RefundEntity:
        """Persist and return the entity."""
        self._store[entity.id] = entity
        return entity

    def update(self, entity: RefundEntity) -> RefundEntity:
        """Overwrite the stored entity and return it."""
        self._store[entity.id] = entity
        return entity


class FakePromoCodeRepository(IPromoCodeRepository):
    """In-memory promo code store. Accepts a single entity, a list, or None."""

    def __init__(self, promos: "PromoCodeEntity | list[PromoCodeEntity] | None" = None) -> None:
        if isinstance(promos, list):
            items: list[PromoCodeEntity] = promos
        elif promos is not None:
            items = [promos]
        else:
            items = []
        self._store: dict[str, PromoCodeEntity] = {p.code.upper(): p for p in items}
        self.incremented: list[uuid.UUID] = []

    def get_by_code(self, code: str) -> PromoCodeEntity:
        """Return the promo if the code matches case-insensitively."""
        promo = self._store.get(code.upper())
        if promo is None:
            raise InvalidPromoCodeError("Promo code not found.")
        return promo

    def increment_usage(self, promo_id: uuid.UUID) -> None:
        """Record that usage was incremented for this promo."""
        self.incremented.append(promo_id)

    def create(self, entity: PromoCodeEntity) -> PromoCodeEntity:
        """Store a new promo code."""
        self._store[entity.code.upper()] = entity
        return entity

    def list_all(self) -> list[PromoCodeEntity]:
        """Return all stored promo codes."""
        return list(self._store.values())


def make_dispute(**kwargs: object) -> DisputeEntity:
    """Build a DisputeEntity with sensible defaults for testing."""
    now = _now()
    defaults: dict = {
        "id": uuid.uuid4(),
        "order_id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "status": "open",
        "reason": "duplicate",
        "description": "Test dispute description.",
        "evidence": {},
        "gateway_dispute_id": "",
        "resolved_at": None,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(kwargs)
    return DisputeEntity(**defaults)  # type: ignore[arg-type]


class FakeDisputeRepository(IDisputeRepository):
    """In-memory dispute store."""

    def __init__(self, disputes: "list[DisputeEntity] | None" = None) -> None:
        self._store: dict[uuid.UUID, DisputeEntity] = {d.id: d for d in (disputes or [])}

    def create(self, entity: DisputeEntity) -> DisputeEntity:
        """Persist and return the entity."""
        self._store[entity.id] = entity
        return entity

    def get_by_id(self, dispute_id: uuid.UUID) -> DisputeEntity:
        """Raise DisputeNotFoundError if absent."""
        entity = self._store.get(dispute_id)
        if entity is None:
            raise DisputeNotFoundError("Dispute not found.")
        return entity

    def list_by_order(self, order_id: uuid.UUID, user_id: uuid.UUID) -> list[DisputeEntity]:
        """Return disputes for the given order owned by this user."""
        return [d for d in self._store.values() if d.order_id == order_id and d.user_id == user_id]

    def update(self, entity: DisputeEntity) -> DisputeEntity:
        """Overwrite the stored entity and return it."""
        self._store[entity.id] = entity
        return entity

    def list_all(self) -> list[DisputeEntity]:
        """Return all disputes, newest first."""
        return sorted(self._store.values(), key=lambda d: d.created_at, reverse=True)


class FakeSubscriptionRepository:
    def __init__(self):
        self._subs = []
        self._active = {}

    def create(self, entity):
        self._subs.append(entity)
        return entity

    def update(self, entity):
        return entity

    def get_active_by_org(self, org_id):
        return self._active.get(org_id)
