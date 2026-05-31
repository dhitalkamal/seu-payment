from __future__ import annotations

import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0004_add_subscription_models"),
    ]

    operations = [
        # RenameIndex generates ALTER INDEX "name" without schema prefix,
        # which is fine now that tables live in the public schema.
        # SeparateDatabaseAndState keeps the migration state in sync via state operations.
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql='ALTER INDEX IF EXISTS "sub_org_id_idx" RENAME TO "payments_su_org_id_bb7c7d_idx"',
                    reverse_sql='ALTER INDEX IF EXISTS "payments_su_org_id_bb7c7d_idx" RENAME TO "sub_org_id_idx"',
                ),
                migrations.RunSQL(
                    sql='ALTER INDEX IF EXISTS "sub_gw_sub_idx" RENAME TO "payments_su_gateway_536e1d_idx"',
                    reverse_sql='ALTER INDEX IF EXISTS "payments_su_gateway_536e1d_idx" RENAME TO "sub_gw_sub_idx"',
                ),
                migrations.RunSQL(
                    sql='ALTER INDEX IF EXISTS "sp_sub_paid_idx" RENAME TO "payments_su_subscri_badb6a_idx"',
                    reverse_sql='ALTER INDEX IF EXISTS "payments_su_subscri_badb6a_idx" RENAME TO "sp_sub_paid_idx"',
                ),
            ],
            state_operations=[
                migrations.RenameIndex(
                    model_name="subscription",
                    new_name="payments_su_org_id_bb7c7d_idx",
                    old_name="sub_org_id_idx",
                ),
                migrations.RenameIndex(
                    model_name="subscription",
                    new_name="payments_su_gateway_536e1d_idx",
                    old_name="sub_gw_sub_idx",
                ),
                migrations.RenameIndex(
                    model_name="subscriptionpayment",
                    new_name="payments_su_subscri_badb6a_idx",
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
