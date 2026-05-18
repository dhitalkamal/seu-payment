"""DRF serializers for payments request deserialization and response shaping."""

from __future__ import annotations

from rest_framework import serializers


class CreateOrderSerializer(serializers.Serializer):
    """Payload for creating a payment order."""

    event_id = serializers.UUIDField()
    registration_id = serializers.UUIDField()
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2)
    gateway = serializers.ChoiceField(choices=["khalti", "esewa", "stripe", "paypal"])
    idempotency_key = serializers.UUIDField()
    promo_code = serializers.CharField(max_length=50, required=False, allow_null=True, default=None)
    # ! org_plan drives the platform fee rate — passed by the frontend from the event/org context
    org_plan = serializers.ChoiceField(
        choices=["free", "starter", "pro", "ngo", "enterprise"],
        required=False,
        default="free",
    )


class RequestRefundSerializer(serializers.Serializer):
    """Payload for requesting a refund on a completed order."""

    order_id = serializers.UUIDField()
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True, default=None
    )
    reason = serializers.CharField()


class PaymentOrderResponseSerializer(serializers.Serializer):
    """Public shape of a payment order resource."""

    id = serializers.UUIDField()
    user_id = serializers.UUIDField()
    event_id = serializers.UUIDField()
    registration_id = serializers.UUIDField()
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2)
    discount_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    tax_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    gateway_fee = serializers.DecimalField(max_digits=12, decimal_places=2)
    platform_fee = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField()
    status = serializers.CharField()
    gateway = serializers.CharField()
    gateway_order_id = serializers.CharField()
    idempotency_key = serializers.UUIDField()
    completed_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class RefundResponseSerializer(serializers.Serializer):
    """Public shape of a refund resource."""

    id = serializers.UUIDField()
    order_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    reason = serializers.CharField()
    status = serializers.CharField()
    gateway_refund_id = serializers.CharField()
    created_at = serializers.DateTimeField()


class KhaltiWebhookSerializer(serializers.Serializer):
    """Khalti payment callback payload."""

    pidx = serializers.CharField(help_text="Khalti payment index (gateway_order_id).")
    transaction_id = serializers.CharField(required=False, default="")
    status = serializers.ChoiceField(choices=["Completed", "Failed", "Pending", "Refunded"])


class EsewaWebhookSerializer(serializers.Serializer):
    """eSewa payment callback payload."""

    product_code = serializers.CharField()
    transaction_uuid = serializers.CharField(help_text="eSewa order ID (gateway_order_id).")
    transaction_code = serializers.CharField(required=False, default="")
    status = serializers.ChoiceField(choices=["COMPLETE", "FAILED", "PENDING", "AMBIGUOUS"])


class CreatePromoCodeSerializer(serializers.Serializer):
    """Payload for creating a promo code."""

    code = serializers.CharField(max_length=50)
    discount_type = serializers.ChoiceField(choices=["percentage", "fixed"])
    discount_value = serializers.DecimalField(max_digits=10, decimal_places=2)
    valid_from = serializers.DateTimeField()
    valid_until = serializers.DateTimeField()
    max_usage_count = serializers.IntegerField(min_value=0, default=0)


class PromoCodeResponseSerializer(serializers.Serializer):
    """Public shape of a promo code resource."""

    id = serializers.UUIDField()
    code = serializers.CharField()
    discount_type = serializers.CharField()
    discount_value = serializers.DecimalField(max_digits=10, decimal_places=2)
    valid_from = serializers.DateTimeField()
    valid_until = serializers.DateTimeField()
    is_active = serializers.BooleanField()
    max_usage_count = serializers.IntegerField()
    used_count = serializers.IntegerField()
    created_at = serializers.DateTimeField()


class CreateDisputeSerializer(serializers.Serializer):
    """Payload for opening a dispute against a completed order."""

    reason = serializers.ChoiceField(
        choices=["duplicate", "fraudulent", "not_received", "subscription_cancelled", "other"]
    )
    description = serializers.CharField(max_length=2000)
    evidence = serializers.DictField(required=False, default=dict)


class UpdateDisputeStatusSerializer(serializers.Serializer):
    """Payload for advancing a dispute's lifecycle status (admin only)."""

    status = serializers.ChoiceField(
        choices=["open", "under_review", "resolved", "closed"]
    )
    resolution_notes = serializers.CharField(max_length=2000, required=False, default="")


class DisputeResponseSerializer(serializers.Serializer):
    """Public shape of a dispute resource."""

    id = serializers.UUIDField()
    order_id = serializers.UUIDField()
    user_id = serializers.UUIDField()
    status = serializers.CharField()
    reason = serializers.CharField()
    description = serializers.CharField()
    evidence = serializers.DictField()
    gateway_dispute_id = serializers.CharField()
    resolved_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


# * ---- Subscription serializers ----


class CreateSubscriptionSerializer(serializers.Serializer):
    """Payload for subscribing an org to a plan."""

    org_id = serializers.UUIDField()
    plan = serializers.ChoiceField(choices=["starter", "pro", "ngo", "enterprise"])
    gateway = serializers.ChoiceField(choices=["khalti", "esewa", "stripe", "paypal"])


class CancelSubscriptionSerializer(serializers.Serializer):
    """Payload for cancelling an org's active subscription."""

    org_id = serializers.UUIDField()


class SubscriptionResponseSerializer(serializers.Serializer):
    """Public shape of a subscription resource."""

    id = serializers.UUIDField()
    org_id = serializers.UUIDField()
    plan = serializers.CharField()
    status = serializers.CharField()
    gateway = serializers.CharField()
    gateway_subscription_id = serializers.CharField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField()
    current_period_start = serializers.DateTimeField()
    current_period_end = serializers.DateTimeField()
    cancelled_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class SubscriptionPaymentResponseSerializer(serializers.Serializer):
    """Public shape of a subscription payment record."""

    id = serializers.UUIDField()
    subscription_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField()
    status = serializers.CharField()
    gateway_transaction_id = serializers.CharField()
    period_start = serializers.DateTimeField()
    period_end = serializers.DateTimeField()
    paid_at = serializers.DateTimeField()
