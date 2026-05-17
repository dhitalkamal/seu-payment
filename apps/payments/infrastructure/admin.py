"""Django admin registrations for payments domain models."""

from __future__ import annotations

from django.contrib import admin

from apps.payments.infrastructure.models import PaymentOrder, PromoCode, Refund

admin.site.register(PaymentOrder)
admin.site.register(Refund)
admin.site.register(PromoCode)
