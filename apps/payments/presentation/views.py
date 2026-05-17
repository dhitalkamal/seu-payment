"""DRF API views for payments endpoints."""

from __future__ import annotations

import uuid

from django.conf import settings
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.api.responses import created_response, error_response, success_response
from apps.common.health import check_database, check_rabbitmq, check_redis
from apps.payments.application.use_cases.create_order import CreatePaymentOrderUseCase
from apps.payments.application.use_cases.get_order import GetOrderUseCase
from apps.payments.application.use_cases.list_my_orders import ListMyOrdersUseCase
from apps.payments.application.use_cases.request_refund import RequestRefundUseCase
from apps.payments.infrastructure.repositories import (
    DjangoPaymentOrderRepository,
    DjangoPromoCodeRepository,
    DjangoRefundRepository,
)
from apps.payments.application.use_cases.process_webhook import ProcessWebhookUseCase
from apps.payments.infrastructure.publisher import publish_event
from apps.payments.presentation.serializers import (
    CreateOrderSerializer,
    EsewaWebhookSerializer,
    KhaltiWebhookSerializer,
    PaymentOrderResponseSerializer,
    RefundResponseSerializer,
    RequestRefundSerializer,
)

_IS_AUTH = IsAuthenticated
_CREATED = created_response
_UUID = uuid.UUID
_CREATE_ORDER_UC = CreatePaymentOrderUseCase
_GET_ORDER_UC = GetOrderUseCase
_LIST_ORDERS_UC = ListMyOrdersUseCase
_REFUND_UC = RequestRefundUseCase
_ORDER_REPO = DjangoPaymentOrderRepository
_PROMO_REPO = DjangoPromoCodeRepository
_REFUND_REPO = DjangoRefundRepository
_CREATE_ORDER_SER = CreateOrderSerializer
_ORDER_RESP_SER = PaymentOrderResponseSerializer
_REFUND_RESP_SER = RefundResponseSerializer
_REFUND_SER = RequestRefundSerializer
_WEBHOOK_UC = ProcessWebhookUseCase
_KHALTI_SER = KhaltiWebhookSerializer
_ESEWA_SER = EsewaWebhookSerializer

_CHECKS = inline_serializer(
    name="DependencyChecks",
    fields={
        "database": serializers.ChoiceField(choices=["healthy", "unhealthy"]),
        "redis": serializers.ChoiceField(choices=["healthy", "unhealthy"]),
        "rabbitmq": serializers.ChoiceField(choices=["healthy", "unhealthy"]),
    },
)
_META_SCHEMA = inline_serializer(
    name="ResponseMeta",
    fields={
        "request_id": serializers.CharField(),
        "timestamp": serializers.CharField(),
    },
)


class HealthCheckView(APIView):
    """Reports the operational status of all external dependencies."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Health"],
        summary="Service health check",
        description=(
            "Checks connectivity to PostgreSQL, Redis, and RabbitMQ. "
            "Returns 200 when all dependencies are healthy, 503 when any are down."
        ),
        auth=[],
        responses={
            200: OpenApiResponse(
                description="All dependencies are healthy.",
                response=inline_serializer(
                    name="HealthyResponse",
                    fields={
                        "data": inline_serializer(
                            name="HealthyData",
                            fields={
                                "service": serializers.CharField(),
                                "status": serializers.CharField(),
                                "version": serializers.CharField(),
                                "checks": _CHECKS,
                            },
                        ),
                        "error": serializers.JSONField(allow_null=True),
                        "meta": _META_SCHEMA,
                    },
                ),
            ),
            503: OpenApiResponse(
                description="One or more dependencies are unavailable.",
                response=inline_serializer(
                    name="UnhealthyResponse",
                    fields={
                        "data": serializers.JSONField(allow_null=True),
                        "error": inline_serializer(
                            name="HealthError",
                            fields={
                                "code": serializers.CharField(),
                                "message": serializers.CharField(),
                                "details": serializers.JSONField(allow_null=True),
                            },
                        ),
                        "meta": _META_SCHEMA,
                    },
                ),
            ),
        },
    )
    def get(self, request: Request) -> Response:
        """Check DB, Redis, and RabbitMQ and return an aggregated status."""
        db_status, db_err = check_database()
        redis_status, redis_err = check_redis()
        rmq_status, rmq_err = check_rabbitmq()

        checks: dict = {
            "database": db_status,
            "redis": redis_status,
            "rabbitmq": rmq_status,
        }
        dep_errors: dict = {
            k: v
            for k, v in {
                "database": db_err,
                "redis": redis_err,
                "rabbitmq": rmq_err,
            }.items()
            if v is not None
        }

        all_healthy = all(s == "healthy" for s in checks.values())

        if all_healthy:
            return success_response(
                {
                    "service": settings.SERVICE_NAME,
                    "status": "healthy",
                    "version": "0.1.0",
                    "checks": checks,
                },
                request=request,
            )

        return error_response(
            code="ERR_SERVICE_UNHEALTHY",
            message="One or more dependencies are unavailable.",
            details={"checks": checks, **({"errors": dep_errors} if dep_errors else {})},
            http_status=503,
            request=request,
        )


class CreateOrderView(APIView):
    """List own orders (GET) or create a payment order (POST)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Orders"],
        summary="List my orders",
        description="Returns all orders for the authenticated user, newest first.",
        responses={
            200: OpenApiResponse(
                description="User orders.", response=_ORDER_RESP_SER(many=True)
            ),
            401: OpenApiResponse(description="Missing or invalid JWT."),
        },
    )
    def get(self, request: Request) -> Response:
        """Return all orders owned by the authenticated user."""
        results = _LIST_ORDERS_UC(_ORDER_REPO()).execute(
            user_id=_UUID(str(request.user.id)),
        )
        return success_response(_ORDER_RESP_SER(results, many=True).data, request=request)

    @extend_schema(
        tags=["Orders"],
        summary="Create a payment order",
        description=(
            "Creates an order with 5% platform fee applied. "
            "Submitting the same idempotency_key returns the existing order. "
            "Optionally supply a promo_code for a discount."
        ),
        request=_CREATE_ORDER_SER,
        responses={
            201: OpenApiResponse(description="Order created.", response=_ORDER_RESP_SER),
            401: OpenApiResponse(description="Missing or invalid JWT."),
            409: OpenApiResponse(description="Order already exists for this registration."),
            422: OpenApiResponse(description="Invalid promo code."),
        },
    )
    def post(self, request: Request) -> Response:
        """Validate payload, compute fees, and persist the order."""
        ser = _CREATE_ORDER_SER(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        result = _CREATE_ORDER_UC(
            order_repo=_ORDER_REPO(),
            promo_repo=_PROMO_REPO(),
        ).execute(
            user_id=_UUID(str(request.user.id)),
            event_id=d["event_id"],
            registration_id=d["registration_id"],
            subtotal=d["subtotal"],
            gateway=d["gateway"],
            idempotency_key=d["idempotency_key"],
            promo_code=d["promo_code"],
        )
        return _CREATED(_ORDER_RESP_SER(result).data, request=request)


class RequestRefundView(APIView):
    """Request a refund on a completed payment order."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Refunds"],
        summary="Request a refund",
        description="Creates a PENDING refund. Only COMPLETED orders can be refunded.",
        request=_REFUND_SER,
        responses={
            201: OpenApiResponse(description="Refund requested.", response=_REFUND_RESP_SER),
            401: OpenApiResponse(description="Missing or invalid JWT."),
            404: OpenApiResponse(description="Order not found."),
            422: OpenApiResponse(description="Order is not in completed status."),
        },
    )
    def post(self, request: Request) -> Response:
        """Validate ownership and status, then create a pending refund."""
        ser = _REFUND_SER(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        result = _REFUND_UC(
            order_repo=_ORDER_REPO(),
            refund_repo=_REFUND_REPO(),
        ).execute(
            order_id=d["order_id"],
            user_id=_UUID(str(request.user.id)),
            amount=d["amount"],
            reason=d["reason"],
        )
        return _CREATED(_REFUND_RESP_SER(result).data, request=request)


class OrderDetailView(APIView):
    """Retrieve a single payment order owned by the authenticated user."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Orders"],
        summary="Get order by id",
        responses={
            200: OpenApiResponse(description="Order found.", response=_ORDER_RESP_SER),
            401: OpenApiResponse(description="Missing or invalid JWT."),
            404: OpenApiResponse(description="Order not found."),
        },
    )
    def get(self, request: Request, order_id: uuid.UUID) -> Response:
        """Return the order if it exists and belongs to the authenticated user."""
        result = _GET_ORDER_UC(_ORDER_REPO()).execute(
            order_id=order_id,
            user_id=_UUID(str(request.user.id)),
        )
        return success_response(_ORDER_RESP_SER(result).data, request=request)


class KhaltiWebhookView(APIView):
    """Receive payment status callbacks from Khalti."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Webhooks"],
        summary="Khalti payment webhook",
        auth=[],
        request=_KHALTI_SER,
        responses={200: OpenApiResponse(description="Webhook processed.")},
    )
    def post(self, request: Request) -> Response:
        """Process the Khalti callback and update the matching order."""
        ser = _KHALTI_SER(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        khalti_to_internal = {"Completed": "completed", "Failed": "failed"}
        internal_status = khalti_to_internal.get(d["status"], "processing")

        order = _WEBHOOK_UC(_ORDER_REPO()).execute(
            gateway_order_id=d["pidx"],
            status=internal_status,
            gateway_transaction_id=d.get("transaction_id", ""),
        )
        if order.status == "completed":
            publish_event(
                routing_key="payment.order.completed",
                payload={
                    "order_id": str(order.id),
                    "registration_id": str(order.registration_id),
                    "user_id": str(order.user_id),
                    "event_id": str(order.event_id),
                },
            )
        return success_response({"received": True}, request=request)


class EsewaWebhookView(APIView):
    """Receive payment status callbacks from eSewa."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Webhooks"],
        summary="eSewa payment webhook",
        auth=[],
        request=_ESEWA_SER,
        responses={200: OpenApiResponse(description="Webhook processed.")},
    )
    def post(self, request: Request) -> Response:
        """Process the eSewa callback and update the matching order."""
        ser = _ESEWA_SER(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        esewa_to_internal = {"COMPLETE": "completed", "FAILED": "failed"}
        internal_status = esewa_to_internal.get(d["status"], "processing")

        order = _WEBHOOK_UC(_ORDER_REPO()).execute(
            gateway_order_id=d["transaction_uuid"],
            status=internal_status,
            gateway_transaction_id=d.get("transaction_code", ""),
        )
        if order.status == "completed":
            publish_event(
                routing_key="payment.order.completed",
                payload={
                    "order_id": str(order.id),
                    "registration_id": str(order.registration_id),
                    "user_id": str(order.user_id),
                    "event_id": str(order.event_id),
                },
            )
        return success_response({"received": True}, request=request)


