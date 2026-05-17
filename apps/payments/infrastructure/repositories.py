"""Concrete repository implementations backed by the Django ORM."""

from __future__ import annotations

import uuid

from django.db import models as django_models

from apps.payments.domain.entities import PaymentOrderEntity, PromoCodeEntity, RefundEntity
from apps.payments.domain.exceptions import InvalidPromoCodeError, OrderNotFoundError
from apps.payments.domain.repositories import (
    IPaymentOrderRepository,
    IPromoCodeRepository,
    IRefundRepository,
)
from apps.payments.infrastructure.models import PaymentOrder, PromoCode, Refund


class DjangoPaymentOrderRepository(IPaymentOrderRepository):
    """Persists PaymentOrder entities using the Django ORM."""

    def create(self, entity: PaymentOrderEntity) -> PaymentOrderEntity:
        """Persist a new order and return the saved entity."""
        obj = PaymentOrder.from_entity(entity)
        obj.save(using="default")
        return obj.to_entity()

    def get_by_id(self, order_id: uuid.UUID, user_id: uuid.UUID) -> PaymentOrderEntity:
        """Fetch by id and user. Raises OrderNotFoundError if absent or not owned."""
        try:
            return PaymentOrder.objects.get(id=order_id, user_id=user_id).to_entity()
        except PaymentOrder.DoesNotExist:
            raise OrderNotFoundError("Order not found.")

    def get_by_idempotency_key(self, key: uuid.UUID) -> PaymentOrderEntity | None:
        """Return the order with this key, or None."""
        try:
            return PaymentOrder.objects.get(idempotency_key=key).to_entity()
        except PaymentOrder.DoesNotExist:
            return None

    def has_order_for_registration(self, registration_id: uuid.UUID) -> bool:
        """True if any order exists for this registration."""
        return PaymentOrder.objects.filter(registration_id=registration_id).exists()

    def update(self, entity: PaymentOrderEntity) -> PaymentOrderEntity:
        """Fetch the existing row, update mutable fields, and save."""
        obj = PaymentOrder.objects.get(id=entity.id)
        obj.status = entity.status
        obj.completed_at = entity.completed_at
        obj.gateway_order_id = entity.gateway_order_id
        obj.save()
        return obj.to_entity()


class DjangoRefundRepository(IRefundRepository):
    """Persists Refund entities using the Django ORM."""

    def create(self, entity: RefundEntity) -> RefundEntity:
        """Persist a new refund and return the saved entity."""
        obj = Refund.from_entity(entity)
        obj.save(using="default")
        return obj.to_entity()


class DjangoPromoCodeRepository(IPromoCodeRepository):
    """Persists PromoCode lookups using the Django ORM."""

    def get_by_code(self, code: str) -> PromoCodeEntity:
        """Fetch by case-insensitive code. Raises InvalidPromoCodeError if absent."""
        try:
            return PromoCode.objects.get(code__iexact=code).to_entity()
        except PromoCode.DoesNotExist:
            raise InvalidPromoCodeError("Promo code not found.")

    def increment_usage(self, promo_id: uuid.UUID) -> None:
        """Atomically increment used_count by 1."""
        PromoCode.objects.filter(id=promo_id).update(used_count=django_models.F("used_count") + 1)
