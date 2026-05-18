"""URL routes for the payments app."""

from __future__ import annotations

from django.urls import URLPattern, path

from .views import (
    CreateOrderView,
    DisputeDetailView,
    DisputeListCreateView,
    EsewaWebhookView,
    HealthCheckView,
    KhaltiWebhookView,
    OrderDetailView,
    PromoCodeListCreateView,
    RequestRefundView,
    ValidatePromoCodeView,
)

urlpatterns: list[URLPattern] = [
    path("health/", HealthCheckView.as_view(), name="health"),
    path("orders/", CreateOrderView.as_view(), name="order-list-create"),
    path("orders/<uuid:order_id>/", OrderDetailView.as_view(), name="order-detail"),
    path(
        "orders/<uuid:order_id>/disputes/",
        DisputeListCreateView.as_view(),
        name="dispute-list-create",
    ),
    path(
        "disputes/<uuid:dispute_id>/",
        DisputeDetailView.as_view(),
        name="dispute-detail",
    ),
    path("refunds/", RequestRefundView.as_view(), name="request-refund"),
    path("webhooks/khalti/", KhaltiWebhookView.as_view(), name="webhook-khalti"),
    path("webhooks/esewa/", EsewaWebhookView.as_view(), name="webhook-esewa"),
    path("promo-codes/", PromoCodeListCreateView.as_view(), name="promo-code-list-create"),
    path(
        "promo-codes/<str:code>/validate/",
        ValidatePromoCodeView.as_view(),
        name="promo-code-validate",
    ),
]
