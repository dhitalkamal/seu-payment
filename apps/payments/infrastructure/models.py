"""Django ORM models for the payments domain. Maps to the payments schema."""

from __future__ import annotations

import uuid
from decimal import Decimal

from django.db import models

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


class PaymentOrder(models.Model):
    """A payment order for a single event registration."""

    class Status(models.TextChoices):
        CREATED = "created", "Created"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"
        CANCELLED = "cancelled", "Cancelled"

    class Gateway(models.TextChoices):
        KHALTI = "khalti", "Khalti"
        ESEWA = "esewa", "eSewa"
        STRIPE = "stripe", "Stripe"
        PAYPAL = "paypal", "PayPal"

    class Meta:
        db_table = "payments_payment_order"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.UUIDField()
    event_id = models.UUIDField()
    registration_id = models.UUIDField(unique=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    gateway_fee = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    platform_fee = models.DecimalField(max_digits=12, decimal_places=2)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="NPR")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CREATED)
    gateway = models.CharField(max_length=20, choices=Gateway.choices)
    gateway_order_id = models.CharField(max_length=255, blank=True)
    idempotency_key = models.UUIDField(unique=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    # * stored so notification-service has the buyer's email when the webhook fires
    customer_email = models.EmailField(blank=True, default="")
    customer_first_name = models.CharField(max_length=150, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def to_entity(self) -> PaymentOrderEntity:
        """Map this ORM row to a pure-Python PaymentOrderEntity."""
        return PaymentOrderEntity(
            id=self.id,
            user_id=self.user_id,
            event_id=self.event_id,
            registration_id=self.registration_id,
            subtotal=self.subtotal,
            discount_amount=self.discount_amount,
            tax_amount=self.tax_amount,
            gateway_fee=self.gateway_fee,
            platform_fee=self.platform_fee,
            total_amount=self.total_amount,
            currency=self.currency,
            status=self.status,
            gateway=self.gateway,
            gateway_order_id=self.gateway_order_id,
            idempotency_key=self.idempotency_key,
            created_at=self.created_at,
            updated_at=self.updated_at,
            completed_at=self.completed_at,
            customer_email=self.customer_email or "",
            customer_first_name=self.customer_first_name or "",
        )

    @classmethod
    def from_entity(cls, entity: PaymentOrderEntity) -> "PaymentOrder":
        """Build an unsaved ORM instance from a PaymentOrderEntity."""
        return cls(
            id=entity.id,
            user_id=entity.user_id,
            event_id=entity.event_id,
            registration_id=entity.registration_id,
            subtotal=entity.subtotal,
            discount_amount=entity.discount_amount,
            tax_amount=entity.tax_amount,
            gateway_fee=entity.gateway_fee,
            platform_fee=entity.platform_fee,
            total_amount=entity.total_amount,
            currency=entity.currency,
            status=entity.status,
            gateway=entity.gateway,
            gateway_order_id=entity.gateway_order_id,
            idempotency_key=entity.idempotency_key,
            completed_at=entity.completed_at,
            customer_email=entity.customer_email,
            customer_first_name=entity.customer_first_name,
        )


class Refund(models.Model):
    """A refund request against a completed payment order."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    class Meta:
        db_table = "payments_refund"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(PaymentOrder, on_delete=models.PROTECT, related_name="refunds")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    gateway_refund_id = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def to_entity(self) -> RefundEntity:
        """Map this ORM row to a pure-Python RefundEntity."""
        return RefundEntity(
            id=self.id,
            order_id=self.order_id,
            amount=self.amount,
            reason=self.reason,
            status=self.status,
            gateway_refund_id=self.gateway_refund_id,
            created_at=self.created_at,
        )

    @classmethod
    def from_entity(cls, entity: RefundEntity) -> "Refund":
        """Build an unsaved ORM instance from a RefundEntity."""
        return cls(
            id=entity.id,
            order_id=entity.order_id,
            amount=entity.amount,
            reason=entity.reason,
            status=entity.status,
            gateway_refund_id=entity.gateway_refund_id,
        )


class PromoCode(models.Model):
    """A discount code applied at order creation time."""

    class DiscountType(models.TextChoices):
        PERCENTAGE = "percentage", "Percentage"
        FIXED_AMOUNT = "fixed_amount", "Fixed Amount"

    class Meta:
        db_table = "payments_promo_code"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True)
    discount_type = models.CharField(max_length=20, choices=DiscountType.choices)
    discount_value = models.DecimalField(max_digits=12, decimal_places=2)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    max_usage_count = models.PositiveIntegerField(default=100)
    used_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def to_entity(self) -> PromoCodeEntity:
        """Map this ORM row to a pure-Python PromoCodeEntity."""
        return PromoCodeEntity(
            id=self.id,
            code=self.code,
            discount_type=self.discount_type,
            discount_value=self.discount_value,
            valid_from=self.valid_from,
            valid_until=self.valid_until,
            is_active=self.is_active,
            max_usage_count=self.max_usage_count,
            used_count=self.used_count,
            created_at=self.created_at,
        )

    @classmethod
    def from_entity(cls, entity: PromoCodeEntity) -> "PromoCode":
        """Build an unsaved ORM instance from a PromoCodeEntity."""
        return cls(
            id=entity.id,
            code=entity.code,
            discount_type=entity.discount_type,
            discount_value=entity.discount_value,
            valid_from=entity.valid_from,
            valid_until=entity.valid_until,
            is_active=entity.is_active,
            max_usage_count=entity.max_usage_count,
            used_count=entity.used_count,
        )


class Dispute(models.Model):
    """A payment dispute raised by an attendee or gateway."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        UNDER_REVIEW = "under_review", "Under Review"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"

    class Reason(models.TextChoices):
        DUPLICATE = "duplicate", "Duplicate charge"
        FRAUDULENT = "fraudulent", "Fraudulent"
        NOT_RECEIVED = "not_received", "Product not received"
        SUBSCRIPTION = "subscription_cancelled", "Subscription cancelled"
        OTHER = "other", "Other"

    class Meta:
        db_table = "payments_dispute"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(PaymentOrder, on_delete=models.CASCADE, related_name="disputes")
    user_id = models.UUIDField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    reason = models.CharField(max_length=30, choices=Reason.choices, default=Reason.OTHER)
    description = models.TextField()
    evidence = models.JSONField(default=dict, blank=True)
    gateway_dispute_id = models.CharField(max_length=255, blank=True, default="")
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def to_entity(self) -> DisputeEntity:
        """Map this ORM row to a pure-Python DisputeEntity."""
        return DisputeEntity(
            id=self.id,
            order_id=self.order_id,
            user_id=self.user_id,
            status=self.status,
            reason=self.reason,
            description=self.description,
            evidence=self.evidence,
            gateway_dispute_id=self.gateway_dispute_id,
            resolved_at=self.resolved_at,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_entity(cls, entity: DisputeEntity) -> "Dispute":
        """Build an unsaved ORM instance from a DisputeEntity."""
        return cls(
            id=entity.id,
            order_id=entity.order_id,
            user_id=entity.user_id,
            status=entity.status,
            reason=entity.reason,
            description=entity.description,
            evidence=entity.evidence,
            gateway_dispute_id=entity.gateway_dispute_id,
            resolved_at=entity.resolved_at,
        )


# * ---- Subscription billing models ----


class Subscription(models.Model):
    """An organization's subscription to a platform plan (recurring billing)."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        CANCELLED = "cancelled", "Cancelled"
        PAST_DUE = "past_due", "Past Due"
        EXPIRED = "expired", "Expired"

    class Plan(models.TextChoices):
        STARTER = "starter", "Starter"
        PRO = "pro", "Pro"
        NGO = "ngo", "NGO"
        ENTERPRISE = "enterprise", "Enterprise"

    class Meta:
        db_table = "payments_subscription"
        indexes = [
            models.Index(fields=["org_id", "-created_at"]),
            models.Index(fields=["gateway_subscription_id"]),
        ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org_id = models.UUIDField()
    plan = models.CharField(max_length=20, choices=Plan.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    gateway = models.CharField(max_length=30)
    gateway_subscription_id = models.CharField(max_length=255, blank=True, default="")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default="NPR")
    current_period_start = models.DateTimeField()
    current_period_end = models.DateTimeField()
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def to_entity(self) -> SubscriptionEntity:
        """Map this ORM row to a pure-Python SubscriptionEntity."""
        return SubscriptionEntity(
            id=self.id,
            org_id=self.org_id,
            plan=self.plan,
            status=self.status,
            gateway=self.gateway,
            gateway_subscription_id=self.gateway_subscription_id,
            amount=self.amount,
            currency=self.currency,
            current_period_start=self.current_period_start,
            current_period_end=self.current_period_end,
            created_at=self.created_at,
            updated_at=self.updated_at,
            cancelled_at=self.cancelled_at,
        )

    @classmethod
    def from_entity(cls, entity: SubscriptionEntity) -> "Subscription":
        """Build an unsaved ORM instance from a SubscriptionEntity."""
        return cls(
            id=entity.id,
            org_id=entity.org_id,
            plan=entity.plan,
            status=entity.status,
            gateway=entity.gateway,
            gateway_subscription_id=entity.gateway_subscription_id,
            amount=entity.amount,
            currency=entity.currency,
            current_period_start=entity.current_period_start,
            current_period_end=entity.current_period_end,
            cancelled_at=entity.cancelled_at,
        )


class SubscriptionPayment(models.Model):
    """A single billing cycle payment within a subscription."""

    class Status(models.TextChoices):
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    class Meta:
        db_table = "payments_subscription_payment"
        indexes = [models.Index(fields=["subscription", "-paid_at"])]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default="NPR")
    status = models.CharField(max_length=20, choices=Status.choices)
    gateway_transaction_id = models.CharField(max_length=255, blank=True, default="")
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    paid_at = models.DateTimeField()

    def to_entity(self) -> SubscriptionPaymentEntity:
        """Map this ORM row to a pure-Python SubscriptionPaymentEntity."""
        return SubscriptionPaymentEntity(
            id=self.id,
            subscription_id=self.subscription_id,
            amount=self.amount,
            currency=self.currency,
            status=self.status,
            gateway_transaction_id=self.gateway_transaction_id,
            period_start=self.period_start,
            period_end=self.period_end,
            paid_at=self.paid_at,
        )

    @classmethod
    def from_entity(cls, entity: SubscriptionPaymentEntity) -> "SubscriptionPayment":
        """Build an unsaved ORM instance from a SubscriptionPaymentEntity."""
        return cls(
            id=entity.id,
            subscription_id=entity.subscription_id,
            amount=entity.amount,
            currency=entity.currency,
            status=entity.status,
            gateway_transaction_id=entity.gateway_transaction_id,
            period_start=entity.period_start,
            period_end=entity.period_end,
            paid_at=entity.paid_at,
        )


# * ---- Stripe Connect ORM models ----


class ConnectedAccount(models.Model):
    """A Stripe Express connected account belonging to an organiser org."""

    class Meta:
        db_table = "payments_connected_account"
        indexes = [
            models.Index(fields=["org_id"], name="idx_connected_account_org"),
        ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org_id = models.UUIDField(unique=True)
    stripe_account_id = models.CharField(max_length=255, unique=True)
    onboarding_url = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def to_entity(self) -> ConnectedAccountEntity:
        """Map this ORM row to a pure-Python ConnectedAccountEntity."""
        return ConnectedAccountEntity(
            id=self.id,
            org_id=self.org_id,
            stripe_account_id=self.stripe_account_id,
            onboarding_url=self.onboarding_url,
            is_active=self.is_active,
            created_at=self.created_at,
        )

    @classmethod
    def from_entity(cls, entity: ConnectedAccountEntity) -> "ConnectedAccount":
        """Build an unsaved ORM instance from a ConnectedAccountEntity."""
        return cls(
            id=entity.id,
            org_id=entity.org_id,
            stripe_account_id=entity.stripe_account_id,
            onboarding_url=entity.onboarding_url,
            is_active=entity.is_active,
        )


class Payout(models.Model):
    """A fund transfer sent to an organiser's connected Stripe account."""

    class Meta:
        db_table = "payments_payout"
        indexes = [
            models.Index(fields=["org_id", "-created_at"], name="idx_payout_org_created"),
        ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org_id = models.UUIDField()
    stripe_account_id = models.CharField(max_length=255)
    stripe_transfer_id = models.CharField(max_length=255, unique=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default="USD")
    description = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def to_entity(self) -> PayoutEntity:
        """Map this ORM row to a pure-Python PayoutEntity."""
        return PayoutEntity(
            id=self.id,
            org_id=self.org_id,
            stripe_account_id=self.stripe_account_id,
            stripe_transfer_id=self.stripe_transfer_id,
            amount=self.amount,
            currency=self.currency,
            description=self.description,
            created_at=self.created_at,
        )

    @classmethod
    def from_entity(cls, entity: PayoutEntity) -> "Payout":
        """Build an unsaved ORM instance from a PayoutEntity."""
        return cls(
            id=entity.id,
            org_id=entity.org_id,
            stripe_account_id=entity.stripe_account_id,
            stripe_transfer_id=entity.stripe_transfer_id,
            amount=entity.amount,
            currency=entity.currency,
            description=entity.description,
        )
