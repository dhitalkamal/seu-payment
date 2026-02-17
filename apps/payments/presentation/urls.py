"""URL routes for the payments app."""

from __future__ import annotations

from django.urls import URLPattern, path

from .views import (
    AdminOrderListView,
    CreateOrderView,
    DisputeDetailView,
    DisputeListAllView,
    DisputeListCreateView,
    EsewaWebhookView,
    HealthCheckView,
    KhaltiWebhookView,
    OrderDetailView,
    PaymentCallbackView,
    PayPalWebhookView,
    PromoCodeListCreateView,
    RequestRefundView,
    StripeWebhookView,
    SubscriptionCancelView,
    SubscriptionCreateView,
    SubscriptionCurrentView,
    SubscriptionPaymentHistoryView,
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
    path("disputes/", DisputeListAllView.as_view(), name="dispute-list-all"),
    path(
        "disputes/<uuid:dispute_id>/",
        DisputeDetailView.as_view(),
        name="dispute-detail",
    ),
    path("refunds/", RequestRefundView.as_view(), name="request-refund"),
    path("webhooks/khalti/", KhaltiWebhookView.as_view(), name="webhook-khalti"),
    path("webhooks/esewa/", EsewaWebhookView.as_view(), name="webhook-esewa"),
    path("webhooks/stripe/", StripeWebhookView.as_view(), name="webhook-stripe"),
    path("webhooks/paypal/", PayPalWebhookView.as_view(), name="webhook-paypal"),
    path("callbacks/<str:gateway>/", PaymentCallbackView.as_view(), name="payment-callback"),
    # * subscription billing
    path("subscriptions/", SubscriptionCreateView.as_view(), name="subscription-create"),
    path("subscriptions/current/", SubscriptionCurrentView.as_view(), name="subscription-current"),
    path("subscriptions/cancel/", SubscriptionCancelView.as_view(), name="subscription-cancel"),
    path(
        "subscriptions/<uuid:subscription_id>/payments/",
        SubscriptionPaymentHistoryView.as_view(),
        name="subscription-payments",
    ),
    path("admin/orders/", AdminOrderListView.as_view(), name="admin-orders"),
    path("promo-codes/", PromoCodeListCreateView.as_view(), name="promo-code-list-create"),
    path(
        "promo-codes/<str:code>/validate/",
        ValidatePromoCodeView.as_view(),
        name="promo-code-validate",
    ),
]
