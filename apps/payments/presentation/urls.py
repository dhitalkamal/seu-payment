"""URL routes for the payments app."""

from __future__ import annotations

from django.urls import URLPattern, path

from .views import CreateOrderView, HealthCheckView, RequestRefundView

urlpatterns: list[URLPattern] = [
    path("health/", HealthCheckView.as_view(), name="health"),
    path("orders/", CreateOrderView.as_view(), name="create-order"),
    path("refunds/", RequestRefundView.as_view(), name="request-refund"),
]
