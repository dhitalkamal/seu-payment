"""Migration: add Subscription and SubscriptionPayment tables for org billing."""

from __future__ import annotations

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0003_add_dispute_user_id"),
    ]

    operations = [
        migrations.CreateModel(
            name="Subscription",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("org_id", models.UUIDField()),
                ("plan", models.CharField(choices=[("starter", "Starter"), ("pro", "Pro"), ("ngo", "NGO"), ("enterprise", "Enterprise")], max_length=20)),
                ("status", models.CharField(choices=[("active", "Active"), ("cancelled", "Cancelled"), ("past_due", "Past Due"), ("expired", "Expired")], default="active", max_length=20)),
                ("gateway", models.CharField(max_length=30)),
                ("gateway_subscription_id", models.CharField(blank=True, default="", max_length=255)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("currency", models.CharField(default="NPR", max_length=10)),
                ("current_period_start", models.DateTimeField()),
                ("current_period_end", models.DateTimeField()),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "payments_subscription",
                "indexes": [
                    models.Index(fields=["org_id", "-created_at"], name="sub_org_id_idx"),
                    models.Index(fields=["gateway_subscription_id"], name="sub_gw_sub_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="SubscriptionPayment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("subscription", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="payments", to="payments.subscription")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("currency", models.CharField(default="NPR", max_length=10)),
                ("status", models.CharField(choices=[("completed", "Completed"), ("failed", "Failed")], max_length=20)),
                ("gateway_transaction_id", models.CharField(blank=True, default="", max_length=255)),
                ("period_start", models.DateTimeField()),
                ("period_end", models.DateTimeField()),
                ("paid_at", models.DateTimeField()),
            ],
            options={
                "db_table": "payments_subscription_payment",
                "indexes": [
                    models.Index(fields=["subscription", "-paid_at"], name="sp_sub_paid_idx"),
                ],
            },
        ),
    ]
