"""URL routes for the payments app."""

from __future__ import annotations

from django.urls import URLPattern, path

from .views import (
    CreateOrderView,
    EsewaWebhookView,
    HealthCheckView,
    KhaltiWebhookView,
    OrderDetailView,
    RequestRefundView,
)

urlpatterns: list[URLPattern] = [
    path("health/", HealthCheckView.as_view(), name="health"),
    path("orders/", CreateOrderView.as_view(), name="order-list-create"),
    path("orders/<uuid:order_id>/", OrderDetailView.as_view(), name="order-detail"),
    path("refunds/", RequestRefundView.as_view(), name="request-refund"),
    path("webhooks/khalti/", KhaltiWebhookView.as_view(), name="webhook-khalti"),
    path("webhooks/esewa/", EsewaWebhookView.as_view(), name="webhook-esewa"),
]
