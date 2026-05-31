"""Django app config for the payments module."""

from __future__ import annotations

from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    """Registers the payments app with Django."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.payments"
    label = "payments"
