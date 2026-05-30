"""Create payment_order, refund, and promo_code tables."""

from __future__ import annotations

import uuid
from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Initial payments tables."""

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="PaymentOrder",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("user_id", models.UUIDField()),
                ("event_id", models.UUIDField()),
                ("registration_id", models.UUIDField(unique=True)),
                ("subtotal", models.DecimalField(decimal_places=2, max_digits=12)),
                (
                    "discount_amount",
                    models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12),
                ),
                (
                    "tax_amount",
                    models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12),
                ),
                (
                    "gateway_fee",
                    models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12),
                ),
                ("platform_fee", models.DecimalField(decimal_places=2, max_digits=12)),
                ("total_amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("currency", models.CharField(default="NPR", max_length=3)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("created", "Created"),
                            ("processing", "Processing"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                            ("refunded", "Refunded"),
                            ("cancelled", "Cancelled"),
                        ],
                        default="created",
                        max_length=20,
                    ),
                ),
                (
                    "gateway",
                    models.CharField(
                        choices=[
                            ("khalti", "Khalti"),
                            ("esewa", "eSewa"),
                            ("stripe", "Stripe"),
                            ("paypal", "PayPal"),
                        ],
                        max_length=20,
                    ),
                ),
                ("gateway_order_id", models.CharField(blank=True, max_length=255)),
                ("idempotency_key", models.UUIDField(unique=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "payments_payment_order"},
        ),
        migrations.CreateModel(
            name="Refund",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                (
                    "order",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="refunds",
                        to="payments.paymentorder",
                    ),
                ),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("reason", models.TextField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("gateway_refund_id", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "payments_refund"},
        ),
        migrations.CreateModel(
            name="PromoCode",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("code", models.CharField(max_length=50, unique=True)),
                (
                    "discount_type",
                    models.CharField(
                        choices=[("percentage", "Percentage"), ("fixed_amount", "Fixed Amount")],
                        max_length=20,
                    ),
                ),
                ("discount_value", models.DecimalField(decimal_places=2, max_digits=12)),
                ("valid_from", models.DateTimeField()),
                ("valid_until", models.DateTimeField()),
                ("is_active", models.BooleanField(default=True)),
                ("max_usage_count", models.PositiveIntegerField(default=100)),
                ("used_count", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "payments_promo_code"},
        ),
    ]
