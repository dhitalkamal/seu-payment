"""Migration: add customer_email and customer_first_name to payment_order."""

from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    """Adds customer_email and customer_first_name to payments.payment_order."""

    dependencies = [
        ("payments", "0006_add_stripe_connect"),
    ]

    operations = [
        migrations.AddField(
            model_name="paymentorder",
            name="customer_email",
            field=models.EmailField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="paymentorder",
            name="customer_first_name",
            field=models.CharField(blank=True, default="", max_length=150),
        ),
    ]
