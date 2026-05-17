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
