"""URL routes for the payments app."""

from __future__ import annotations

from django.urls import URLPattern, path

from .views import CreateOrderView, HealthCheckView, OrderDetailView, OrderListView, RequestRefundView

urlpatterns: list[URLPattern] = [
    path("health/", HealthCheckView.as_view(), name="health"),
    path("orders/", OrderListView.as_view(), name="order-list"),
    path("orders/create/", CreateOrderView.as_view(), name="create-order"),
    path("orders/<uuid:order_id>/", OrderDetailView.as_view(), name="order-detail"),
    path("refunds/", RequestRefundView.as_view(), name="request-refund"),
]
