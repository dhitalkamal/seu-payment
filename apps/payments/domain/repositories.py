"""Abstract repository interfaces for the payments module."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from apps.payments.domain.entities import PaymentOrderEntity, PromoCodeEntity, RefundEntity


class IPaymentOrderRepository(ABC):
    """Persistence contract for PaymentOrder aggregates."""

    @abstractmethod
    def create(self, entity: PaymentOrderEntity) -> PaymentOrderEntity: ...

    @abstractmethod
    def get_by_id(self, order_id: uuid.UUID, user_id: uuid.UUID) -> PaymentOrderEntity: ...

    @abstractmethod
    def get_by_idempotency_key(self, key: uuid.UUID) -> PaymentOrderEntity | None: ...

    @abstractmethod
    def has_order_for_registration(self, registration_id: uuid.UUID) -> bool: ...

    @abstractmethod
    def update(self, entity: PaymentOrderEntity) -> PaymentOrderEntity: ...


class IRefundRepository(ABC):
    """Persistence contract for Refund records."""

    @abstractmethod
    def create(self, entity: RefundEntity) -> RefundEntity: ...


class IPromoCodeRepository(ABC):
    """Persistence contract for PromoCode lookups."""

    @abstractmethod
    def get_by_code(self, code: str) -> PromoCodeEntity: ...

    @abstractmethod
    def increment_usage(self, promo_id: uuid.UUID) -> None: ...
