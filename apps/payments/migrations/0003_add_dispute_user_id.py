"""Migration: add user_id to Dispute for per-user filtering without joins."""

from __future__ import annotations

import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0002_add_dispute_and_multicurrency"),
    ]

    operations = [
        migrations.AddField(
            model_name="dispute",
            name="user_id",
            field=models.UUIDField(default=uuid.uuid4),
            preserve_default=False,
        ),
    ]
