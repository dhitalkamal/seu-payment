"""Concrete repository implementations backed by the Django ORM."""

from __future__ import annotations

import uuid

from django.db import models as django_models

from apps.payments.domain.entities import (
    ConnectedAccountEntity,
    DisputeEntity,
    PaymentOrderEntity,
    PayoutEntity,
    PromoCodeEntity,
    RefundEntity,
    SubscriptionEntity,
    SubscriptionPaymentEntity,
)
from apps.payments.domain.exceptions import (
    ConnectedAccountNotFoundError,
    DisputeNotFoundError,
    InvalidPromoCodeError,
    OrderNotFoundError,
    SubscriptionNotFoundError,
)
from apps.payments.domain.repositories import (
    IConnectedAccountRepository,
    IDisputeRepository,
    IPaymentOrderRepository,
    IPayoutRepository,
    IPromoCodeRepository,
    IRefundRepository,
    ISubscriptionPaymentRepository,
    ISubscriptionRepository,
)
from apps.payments.infrastructure.models import (
    ConnectedAccount,
    Dispute,
    PaymentOrder,
    Payout,
    PromoCode,
    Refund,
    Subscription,
    SubscriptionPayment,
)


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

    def get_by_order_id(self, order_id: object) -> PaymentOrderEntity:
        """Fetch by order ID without ownership check. Raises OrderNotFoundError if absent."""
        try:
            return PaymentOrder.objects.get(id=order_id).to_entity()
        except PaymentOrder.DoesNotExist:
            from apps.payments.domain.exceptions import OrderNotFoundError

            raise OrderNotFoundError("Order not found.")

    def get_by_gateway_order_id(self, gateway_order_id: str) -> PaymentOrderEntity | None:
        """Return the order with this gateway_order_id or None."""
        try:
            return PaymentOrder.objects.get(gateway_order_id=gateway_order_id).to_entity()
        except PaymentOrder.DoesNotExist:
            return None

    def list_by_user(self, user_id: object) -> list[PaymentOrderEntity]:
        """Return all orders for this user ordered newest first."""
        return [obj.to_entity() for obj in PaymentOrder.objects.filter(user_id=user_id).order_by("-created_at")]

    def list_all(self) -> list[PaymentOrderEntity]:
        """Return every order across all users, newest first."""
        return [obj.to_entity() for obj in PaymentOrder.objects.all().order_by("-created_at")]


class DjangoRefundRepository(IRefundRepository):
    """Persists Refund entities using the Django ORM."""

    def create(self, entity: RefundEntity) -> RefundEntity:
        """Persist a new refund and return the saved entity."""
        obj = Refund.from_entity(entity)
        obj.save(using="default")
        return obj.to_entity()

    def update(self, entity: RefundEntity) -> RefundEntity:
        """Update status and gateway_refund_id fields on an existing refund record."""
        Refund.objects.filter(id=entity.id).update(
            status=entity.status,
            gateway_refund_id=entity.gateway_refund_id,
        )
        return entity


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

    def create(self, entity: PromoCodeEntity) -> PromoCodeEntity:
        """Persist a new promo code."""
        obj = PromoCode.from_entity(entity)
        obj.save()
        return obj.to_entity()

    def list_all(self) -> list[PromoCodeEntity]:
        """Return all promo codes ordered by creation date."""
        return [p.to_entity() for p in PromoCode.objects.order_by("-created_at")]


class DjangoDisputeRepository(IDisputeRepository):
    """Persists Dispute entities using the Django ORM."""

    def create(self, entity: DisputeEntity) -> DisputeEntity:
        """Persist a new dispute and return the saved entity."""
        obj = Dispute.from_entity(entity)
        obj.save()
        return obj.to_entity()

    def get_by_id(self, dispute_id: uuid.UUID) -> DisputeEntity:
        """Fetch by id. Raises DisputeNotFoundError if absent."""
        try:
            return Dispute.objects.get(id=dispute_id).to_entity()
        except Dispute.DoesNotExist:
            raise DisputeNotFoundError("Dispute not found.")

    def list_by_order(self, order_id: uuid.UUID, user_id: uuid.UUID) -> list[DisputeEntity]:
        """Return disputes for the given order scoped to the user."""
        return [obj.to_entity() for obj in Dispute.objects.filter(order_id=order_id, user_id=user_id).order_by("-created_at")]

    def update(self, entity: DisputeEntity) -> DisputeEntity:
        """Update mutable dispute fields and return the saved entity."""
        obj = Dispute.objects.get(id=entity.id)
        obj.status = entity.status
        obj.evidence = entity.evidence
        obj.resolved_at = entity.resolved_at
        obj.save()
        return obj.to_entity()

    def list_all(self) -> list[DisputeEntity]:
        """Return all disputes platform-wide, newest first."""
        return [obj.to_entity() for obj in Dispute.objects.all().order_by("-created_at")]


# * ---- Subscription repositories ----


class DjangoSubscriptionRepository(ISubscriptionRepository):
    """Persists Subscription entities using the Django ORM."""

    def create(self, entity: SubscriptionEntity) -> SubscriptionEntity:
        """Persist a new subscription and return the saved entity."""
        obj = Subscription.from_entity(entity)
        obj.save(using="default")
        return obj.to_entity()

    def get_by_id(self, sub_id: uuid.UUID) -> SubscriptionEntity:
        """Fetch by id. Raises SubscriptionNotFoundError if absent."""
        try:
            return Subscription.objects.get(id=sub_id).to_entity()
        except Subscription.DoesNotExist:
            raise SubscriptionNotFoundError("Subscription not found.")

    def get_active_by_org(self, org_id: uuid.UUID) -> SubscriptionEntity | None:
        """Return the active subscription for an org, or None."""
        try:
            return Subscription.objects.get(org_id=org_id, status="active").to_entity()
        except Subscription.DoesNotExist:
            return None

    def get_by_gateway_id(self, gateway_subscription_id: str) -> SubscriptionEntity | None:
        """Lookup by gateway subscription ID for webhook matching."""
        try:
            return Subscription.objects.get(gateway_subscription_id=gateway_subscription_id).to_entity()
        except Subscription.DoesNotExist:
            return None

    def update(self, entity: SubscriptionEntity) -> SubscriptionEntity:
        """Update mutable subscription fields and save."""
        obj = Subscription.objects.get(id=entity.id)
        obj.status = entity.status
        obj.plan = entity.plan
        obj.current_period_start = entity.current_period_start
        obj.current_period_end = entity.current_period_end
        obj.cancelled_at = entity.cancelled_at
        obj.gateway_subscription_id = entity.gateway_subscription_id
        obj.save()
        return obj.to_entity()

    def list_by_org(self, org_id: uuid.UUID) -> list[SubscriptionEntity]:
        """Return all subscriptions for an org, newest first."""
        return [obj.to_entity() for obj in Subscription.objects.filter(org_id=org_id).order_by("-created_at")]

    def list_all(self) -> list[SubscriptionEntity]:
        """Return every subscription across all orgs, newest first."""
        return [obj.to_entity() for obj in Subscription.objects.all().order_by("-created_at")]


class DjangoSubscriptionPaymentRepository(ISubscriptionPaymentRepository):
    """Persists SubscriptionPayment records using the Django ORM."""

    def create(self, entity: SubscriptionPaymentEntity) -> SubscriptionPaymentEntity:
        """Persist a subscription payment record."""
        obj = SubscriptionPayment.from_entity(entity)
        obj.save(using="default")
        return obj.to_entity()

    def list_by_subscription(self, sub_id: uuid.UUID) -> list[SubscriptionPaymentEntity]:
        """Return payment records for a subscription, newest first."""
        return [obj.to_entity() for obj in SubscriptionPayment.objects.filter(subscription_id=sub_id).order_by("-paid_at")]


class DjangoConnectedAccountRepository(IConnectedAccountRepository):
    """Persists ConnectedAccount entities using the Django ORM."""

    def create(self, entity: ConnectedAccountEntity) -> ConnectedAccountEntity:
        """Persist a new connected account and return the saved entity."""
        obj = ConnectedAccount.from_entity(entity)
        obj.save(using="default")
        return obj.to_entity()

    def get_by_org(self, org_id: uuid.UUID) -> ConnectedAccountEntity | None:
        """Return the connected account for an org, or None if none exists."""
        try:
            return ConnectedAccount.objects.get(org_id=org_id).to_entity()
        except ConnectedAccount.DoesNotExist:
            return None

    def get_by_id(self, account_id: uuid.UUID) -> ConnectedAccountEntity:
        """Fetch by primary key. Raises ConnectedAccountNotFoundError if absent."""
        try:
            return ConnectedAccount.objects.get(id=account_id).to_entity()
        except ConnectedAccount.DoesNotExist:
            raise ConnectedAccountNotFoundError("Connected account not found.")


class DjangoPayoutRepository(IPayoutRepository):
    """Persists Payout entities using the Django ORM."""

    def create(self, entity: PayoutEntity) -> PayoutEntity:
        """Persist a new payout record and return the saved entity."""
        obj = Payout.from_entity(entity)
        obj.save(using="default")
        return obj.to_entity()

    def list_by_org(self, org_id: uuid.UUID) -> list[PayoutEntity]:
        """Return all payouts for an org, newest first."""
        return [obj.to_entity() for obj in Payout.objects.filter(org_id=org_id).order_by("-created_at")]
