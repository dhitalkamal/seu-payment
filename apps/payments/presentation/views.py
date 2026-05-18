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
from apps.payments.application.use_cases.create_dispute import CreateDisputeUseCase
from apps.payments.application.use_cases.create_order import CreatePaymentOrderUseCase
from apps.payments.application.use_cases.create_promo_code import CreatePromoCodeUseCase
from apps.payments.application.use_cases.get_order import GetOrderUseCase
from apps.payments.application.use_cases.list_disputes import ListDisputesUseCase
from apps.payments.application.use_cases.list_my_orders import ListMyOrdersUseCase
from apps.payments.application.use_cases.list_promo_codes import ListPromoCodesUseCase
from apps.payments.application.use_cases.process_to_processing import TransitionToProcessingUseCase
from apps.payments.application.use_cases.process_webhook import ProcessWebhookUseCase
from apps.payments.application.use_cases.request_refund import RequestRefundUseCase
from apps.payments.application.use_cases.update_dispute_status import UpdateDisputeStatusUseCase
from apps.payments.application.use_cases.validate_promo_code import ValidatePromoCodeUseCase
from apps.payments.domain.exceptions import DisputeNotFoundError, InvalidPromoCodeError
from apps.payments.infrastructure.publisher import publish_event
from apps.payments.infrastructure.repositories import (
    DjangoDisputeRepository,
    DjangoPaymentOrderRepository,
    DjangoPromoCodeRepository,
    DjangoRefundRepository,
)
from apps.payments.infrastructure.webhook_verify import (
    verify_esewa_signature,
    verify_khalti_signature,
)
from apps.payments.presentation.serializers import (
    CreateDisputeSerializer,
    CreateOrderSerializer,
    CreatePromoCodeSerializer,
    DisputeResponseSerializer,
    EsewaWebhookSerializer,
    KhaltiWebhookSerializer,
    PaymentOrderResponseSerializer,
    PromoCodeResponseSerializer,
    RefundResponseSerializer,
    RequestRefundSerializer,
    UpdateDisputeStatusSerializer,
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
_DISPUTE_REPO = DjangoDisputeRepository
_VALIDATE_PROMO_UC = ValidatePromoCodeUseCase
_CREATE_PROMO_UC = CreatePromoCodeUseCase
_LIST_PROMOS_UC = ListPromoCodesUseCase
_CREATE_DISPUTE_UC = CreateDisputeUseCase
_LIST_DISPUTES_UC = ListDisputesUseCase
_UPDATE_DISPUTE_UC = UpdateDisputeStatusUseCase
_CREATE_ORDER_SER = CreateOrderSerializer
_ORDER_RESP_SER = PaymentOrderResponseSerializer
_REFUND_RESP_SER = RefundResponseSerializer
_REFUND_SER = RequestRefundSerializer
_WEBHOOK_UC = ProcessWebhookUseCase
_TO_PROCESSING_UC = TransitionToProcessingUseCase
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
            200: OpenApiResponse(description="User orders.", response=_ORDER_RESP_SER(many=True)),
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
        # transition to processing now that the client will be redirected to the gateway
        result = _TO_PROCESSING_UC(_ORDER_REPO()).execute(order_id=result.id)
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
        sig = request.headers.get("X-Khalti-Signature", "")
        if not verify_khalti_signature(request.body, sig):
            return error_response(
                code="ERR_PAYMENT_INVALID_SIGNATURE",
                message="Webhook signature verification failed.",
                http_status=400,
                request=request,
            )
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
        sig = request.headers.get("X-Esewa-Signature", "")
        if not verify_esewa_signature(request.body, sig):
            return error_response(
                code="ERR_PAYMENT_INVALID_SIGNATURE",
                message="Webhook signature verification failed.",
                http_status=400,
                request=request,
            )
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


class PromoCodeListCreateView(APIView):
    """GET /promo-codes/ - list; POST /promo-codes/ - create."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Promo Codes"],
        summary="List promo codes",
        responses={200: PromoCodeResponseSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        """Return all promo codes."""
        promos = _LIST_PROMOS_UC(_PROMO_REPO()).execute()
        return success_response(
            PromoCodeResponseSerializer(promos, many=True).data, request=request
        )

    @extend_schema(
        tags=["Promo Codes"],
        summary="Create promo code",
        request=CreatePromoCodeSerializer,
        responses={201: PromoCodeResponseSerializer},
    )
    def post(self, request: Request) -> Response:
        """Create a new promo code."""
        ser = CreatePromoCodeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        promo = _CREATE_PROMO_UC(_PROMO_REPO()).execute(
            code=d["code"],
            discount_type=d["discount_type"],
            discount_value=d["discount_value"],
            valid_from=d["valid_from"],
            valid_until=d["valid_until"],
            max_usage_count=d.get("max_usage_count", 0),
        )
        return _CREATED(PromoCodeResponseSerializer(promo).data, request=request)


class ValidatePromoCodeView(APIView):
    """GET /promo-codes/{code}/validate/ - validate a single promo code."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Promo Codes"],
        summary="Validate promo code",
        responses={
            200: PromoCodeResponseSerializer,
            422: OpenApiResponse(description="Code invalid, expired, or exhausted."),
        },
    )
    def get(self, request: Request, code: str) -> Response:
        """Return promo details if valid, or 422 if not."""
        try:
            promo = _VALIDATE_PROMO_UC(_PROMO_REPO()).execute(code=code)
        except InvalidPromoCodeError as exc:
            return error_response(
                code="ERR_PAYMENT_INVALID_PROMO",
                message=str(exc),
                http_status=422,
                request=request,
            )
        return success_response(PromoCodeResponseSerializer(promo).data, request=request)


class DisputeListCreateView(APIView):
    """GET/POST /orders/{order_id}/disputes/ - list or open a dispute."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Disputes"],
        summary="List disputes for an order",
        responses={200: DisputeResponseSerializer(many=True)},
    )
    def get(self, request: Request, order_id: uuid.UUID) -> Response:
        """Return all disputes filed by this user for the given order."""
        disputes = _LIST_DISPUTES_UC(_DISPUTE_REPO()).execute(
            order_id=order_id,
            user_id=_UUID(str(request.user.id)),
        )
        return success_response(
            DisputeResponseSerializer(disputes, many=True).data, request=request
        )

    @extend_schema(
        tags=["Disputes"],
        summary="Open a dispute",
        request=CreateDisputeSerializer,
        responses={
            201: DisputeResponseSerializer,
            404: OpenApiResponse(description="Order not found."),
        },
    )
    def post(self, request: Request, order_id: uuid.UUID) -> Response:
        """Open a new dispute against the given order."""
        ser = CreateDisputeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        dispute = _CREATE_DISPUTE_UC(_ORDER_REPO(), _DISPUTE_REPO()).execute(
            order_id=order_id,
            user_id=_UUID(str(request.user.id)),
            reason=d["reason"],
            description=d["description"],
            evidence=d.get("evidence", {}),
        )
        return _CREATED(DisputeResponseSerializer(dispute).data, request=request)


class DisputeDetailView(APIView):
    """PATCH /disputes/{dispute_id}/ - advance dispute lifecycle (admin)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Disputes"],
        summary="Update dispute status",
        request=UpdateDisputeStatusSerializer,
        responses={
            200: DisputeResponseSerializer,
            404: OpenApiResponse(description="Dispute not found."),
        },
    )
    def patch(self, request: Request, dispute_id: uuid.UUID) -> Response:
        """Update the status of a dispute (admin action)."""
        ser = UpdateDisputeStatusSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        try:
            dispute = _UPDATE_DISPUTE_UC(_DISPUTE_REPO()).execute(
                dispute_id=dispute_id,
                new_status=d["status"],
                resolution_notes=d.get("resolution_notes", ""),
            )
        except DisputeNotFoundError as exc:
            return error_response(
                code=exc.code, message=str(exc), http_status=404, request=request
            )
        return success_response(DisputeResponseSerializer(dispute).data, request=request)
