"""Django ORM models for the payments domain. Maps to the payments schema."""

from __future__ import annotations

import uuid
from decimal import Decimal

from django.db import models

from apps.payments.domain.entities import PaymentOrderEntity, PromoCodeEntity, RefundEntity


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
        db_table = '"payments"."payment_order"'

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
        )


class Refund(models.Model):
    """A refund request against a completed payment order."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    class Meta:
        db_table = '"payments"."refund"'

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
        db_table = '"payments"."promo_code"'

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
        db_table = '"payments"."dispute"'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        PaymentOrder, on_delete=models.CASCADE, related_name="disputes"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    reason = models.CharField(max_length=30, choices=Reason.choices, default=Reason.OTHER)
    description = models.TextField()
    evidence = models.JSONField(default=dict, blank=True)
    gateway_dispute_id = models.CharField(max_length=255, blank=True, default="")
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
