"""Abstract repository interfaces for the payments module."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from apps.payments.domain.entities import (
    DisputeEntity,
    PaymentOrderEntity,
    PromoCodeEntity,
    RefundEntity,
    SubscriptionEntity,
    SubscriptionPaymentEntity,
)


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

    @abstractmethod
    def list_by_user(self, user_id: uuid.UUID) -> list[PaymentOrderEntity]: ...

    @abstractmethod
    def get_by_order_id(self, order_id: uuid.UUID) -> PaymentOrderEntity: ...

    @abstractmethod
    def get_by_gateway_order_id(self, gateway_order_id: str) -> PaymentOrderEntity | None: ...

    @abstractmethod
    def list_all(self) -> list[PaymentOrderEntity]:
        """Return every order across all users, admin only."""
        ...


class IRefundRepository(ABC):
    """Persistence contract for Refund records."""

    @abstractmethod
    def create(self, entity: RefundEntity) -> RefundEntity: ...

    @abstractmethod
    def update(self, entity: RefundEntity) -> RefundEntity: ...


class IPromoCodeRepository(ABC):
    """Persistence contract for PromoCode lookups."""

    @abstractmethod
    def get_by_code(self, code: str) -> PromoCodeEntity: ...

    @abstractmethod
    def increment_usage(self, promo_id: uuid.UUID) -> None: ...

    @abstractmethod
    def create(self, entity: PromoCodeEntity) -> PromoCodeEntity: ...

    @abstractmethod
    def list_all(self) -> list[PromoCodeEntity]: ...


class IDisputeRepository(ABC):
    """Persistence contract for Dispute records."""

    @abstractmethod
    def create(self, entity: DisputeEntity) -> DisputeEntity: ...

    @abstractmethod
    def get_by_id(self, dispute_id: uuid.UUID) -> DisputeEntity: ...

    @abstractmethod
    def list_by_order(self, order_id: uuid.UUID, user_id: uuid.UUID) -> list[DisputeEntity]: ...

    @abstractmethod
    def update(self, entity: DisputeEntity) -> DisputeEntity: ...

    @abstractmethod
    def list_all(self) -> list[DisputeEntity]:
        """Return every dispute across all orders, admin only."""
        ...


class ISubscriptionRepository(ABC):
    """Persistence contract for Subscription aggregates."""

    @abstractmethod
    def create(self, entity: SubscriptionEntity) -> SubscriptionEntity: ...

    @abstractmethod
    def get_by_id(self, sub_id: uuid.UUID) -> SubscriptionEntity: ...

    @abstractmethod
    def get_active_by_org(self, org_id: uuid.UUID) -> SubscriptionEntity | None: ...

    @abstractmethod
    def get_by_gateway_id(self, gateway_subscription_id: str) -> SubscriptionEntity | None: ...

    @abstractmethod
    def update(self, entity: SubscriptionEntity) -> SubscriptionEntity: ...

    @abstractmethod
    def list_by_org(self, org_id: uuid.UUID) -> list[SubscriptionEntity]: ...

    @abstractmethod
    def list_all(self) -> list[SubscriptionEntity]: ...


class ISubscriptionPaymentRepository(ABC):
    """Persistence contract for SubscriptionPayment records."""

    @abstractmethod
    def create(self, entity: SubscriptionPaymentEntity) -> SubscriptionPaymentEntity: ...

    @abstractmethod
    def list_by_subscription(self, sub_id: uuid.UUID) -> list[SubscriptionPaymentEntity]: ...
