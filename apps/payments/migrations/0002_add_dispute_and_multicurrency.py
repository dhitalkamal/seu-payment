"""Migration: add Dispute table and extend currency choices to include USD."""

from __future__ import annotations

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0001_initial"),
    ]

    operations = [
        # Allow USD in addition to NPR
        migrations.AlterField(
            model_name="paymentorder",
            name="currency",
            field=models.CharField(
                choices=[("NPR", "Nepalese Rupee"), ("USD", "US Dollar")],
                default="NPR",
                max_length=3,
            ),
        ),
        migrations.CreateModel(
            name="Dispute",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                (
                    "order",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="disputes",
                        to="payments.paymentorder",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("open", "Open"),
                            ("under_review", "Under Review"),
                            ("resolved", "Resolved"),
                            ("closed", "Closed"),
                        ],
                        default="open",
                        max_length=20,
                    ),
                ),
                (
                    "reason",
                    models.CharField(
                        choices=[
                            ("duplicate", "Duplicate charge"),
                            ("fraudulent", "Fraudulent"),
                            ("not_received", "Product not received"),
                            ("subscription_cancelled", "Subscription cancelled"),
                            ("other", "Other"),
                        ],
                        default="other",
                        max_length=30,
                    ),
                ),
                ("description", models.TextField()),
                ("evidence", models.JSONField(blank=True, default=dict)),
                ("gateway_dispute_id", models.CharField(blank=True, default="", max_length=255)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": '"payments"."dispute"'},
        ),
    ]
