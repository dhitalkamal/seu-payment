from __future__ import annotations

import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0004_add_subscription_models"),
    ]

    operations = [
        # RenameIndex generates ALTER INDEX "name" without schema prefix,
        # which fails when the table lives in the "payments" schema.
        # SeparateDatabaseAndState lets us use fully-qualified SQL for the DB
        # while keeping the migration state in sync via the state operations.
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql='ALTER INDEX IF EXISTS "payments"."sub_org_id_idx" RENAME TO "subscriptio_org_id_c7fda4_idx"',
                    reverse_sql='ALTER INDEX IF EXISTS "payments"."subscriptio_org_id_c7fda4_idx" RENAME TO "sub_org_id_idx"',
                ),
                migrations.RunSQL(
                    sql='ALTER INDEX IF EXISTS "payments"."sub_gw_sub_idx" RENAME TO "subscriptio_gateway_7d2e80_idx"',
                    reverse_sql='ALTER INDEX IF EXISTS "payments"."subscriptio_gateway_7d2e80_idx" RENAME TO "sub_gw_sub_idx"',
                ),
                migrations.RunSQL(
                    sql='ALTER INDEX IF EXISTS "payments"."sp_sub_paid_idx" RENAME TO "subscriptio_subscri_9e26ed_idx"',
                    reverse_sql='ALTER INDEX IF EXISTS "payments"."subscriptio_subscri_9e26ed_idx" RENAME TO "sp_sub_paid_idx"',
                ),
            ],
            state_operations=[
                migrations.RenameIndex(
                    model_name="subscription",
                    new_name="subscriptio_org_id_c7fda4_idx",
                    old_name="sub_org_id_idx",
                ),
                migrations.RenameIndex(
                    model_name="subscription",
                    new_name="subscriptio_gateway_7d2e80_idx",
                    old_name="sub_gw_sub_idx",
                ),
                migrations.RenameIndex(
                    model_name="subscriptionpayment",
                    new_name="subscriptio_subscri_9e26ed_idx",
                    old_name="sp_sub_paid_idx",
                ),
            ],
        ),
        migrations.AlterField(
            model_name="dispute",
            name="id",
            field=models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name="paymentorder",
            name="currency",
            field=models.CharField(default="NPR", max_length=3),
        ),
    ]
