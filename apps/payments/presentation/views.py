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
from apps.common.permissions import IsOrgAdmin, IsOrgOwner, IsSuperAdminFromAllowedIP
from apps.payments.application.use_cases.create_connected_account import CreateConnectedAccountUseCase
from apps.payments.application.use_cases.create_dispute import CreateDisputeUseCase
from apps.payments.application.use_cases.create_order import CreatePaymentOrderUseCase
from apps.payments.application.use_cases.create_payout import CreatePayoutUseCase
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
from apps.payments.infrastructure.audit_publisher import publish_audit
from apps.payments.infrastructure.gateways import get_gateway
from apps.payments.infrastructure.publisher import publish_event
from apps.payments.infrastructure.repositories import (
    DjangoConnectedAccountRepository,
    DjangoDisputeRepository,
    DjangoPaymentOrderRepository,
    DjangoPayoutRepository,
    DjangoPromoCodeRepository,
    DjangoRefundRepository,
)
from apps.payments.infrastructure.webhook_verify import (
    verify_esewa_signature,
    verify_khalti_signature,
    verify_stripe_signature,
)
from apps.payments.presentation.serializers import (
    CancelSubscriptionSerializer,
    CreateDisputeSerializer,
    CreateOrderSerializer,
    CreatePromoCodeSerializer,
    CreateSubscriptionSerializer,
    DisputeResponseSerializer,
    EsewaWebhookSerializer,
    KhaltiWebhookSerializer,
    PaymentOrderResponseSerializer,
    PromoCodeResponseSerializer,
    RefundResponseSerializer,
    RequestRefundSerializer,
    SubscriptionPaymentResponseSerializer,
    SubscriptionResponseSerializer,
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


def _order_completed_payload(order: object) -> dict:
    """Build the payment.order.completed event payload with all notification fields."""
    return {
        "order_id": str(order.id),
        "registration_id": str(order.registration_id),
        "user_id": str(order.user_id),
        "event_id": str(order.event_id),
        "email": order.customer_email,
        "first_name": order.customer_first_name,
        "amount": str(order.total_amount),
        "gateway": order.gateway,
    }


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
        description=("Checks connectivity to PostgreSQL, Redis, and RabbitMQ. Returns 200 when all dependencies are healthy, 503 when any are down."),
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
        description=("Creates an order with 5% platform fee applied. Submitting the same idempotency_key returns the existing order. Optionally supply a promo_code for a discount."),
        request=_CREATE_ORDER_SER,
        responses={
            201: OpenApiResponse(description="Order created.", response=_ORDER_RESP_SER),
            401: OpenApiResponse(description="Missing or invalid JWT."),
            409: OpenApiResponse(description="Order already exists for this registration."),
            422: OpenApiResponse(description="Invalid promo code."),
        },
    )
    def post(self, request: Request) -> Response:
        """Validate payload, compute fees, call gateway, and return the payment URL."""
        ser = _CREATE_ORDER_SER(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        gateway_name = d["gateway"]
        email = request.user.token.get("email", "")
        first_name = request.user.token.get("first_name", "")

        # * build return/cancel URLs - gateway redirects to our callback endpoint,
        # which processes the result and then redirects to the frontend
        base_web = settings.FRONTEND_WEB_URL
        callback_base = settings.PAYMENT_CALLBACK_BASE_URL
        return_url = f"{callback_base}/callbacks/{gateway_name}/"
        cancel_url = f"{base_web}/payment/failure"

        gateway_client = get_gateway(gateway_name)

        order, session = _CREATE_ORDER_UC(
            order_repo=_ORDER_REPO(),
            promo_repo=_PROMO_REPO(),
            gateway_client=gateway_client,
        ).execute(
            user_id=_UUID(str(request.user.id)),
            event_id=d["event_id"],
            registration_id=d["registration_id"],
            subtotal=d["subtotal"],
            gateway=gateway_name,
            idempotency_key=d["idempotency_key"],
            promo_code=d["promo_code"],
            customer_email=email,
            customer_first_name=first_name,
            return_url=return_url,
            cancel_url=cancel_url,
            org_plan=d.get("org_plan", "free"),
        )

        resp_data = _ORDER_RESP_SER(order).data
        if session is not None:
            resp_data["payment_url"] = session.payment_url
            # * eSewa returns form data the client needs to POST
            if gateway_name == "esewa" and "form_data" in session.raw_response:
                resp_data["esewa_form_data"] = session.raw_response["form_data"]
                resp_data["esewa_form_url"] = session.raw_response["form_url"]
        publish_audit(
            request=request,
            user_id=_UUID(str(request.user.id)),
            event_type="order.created",
            metadata={
                "event_id": str(d["event_id"]),
                "gateway": gateway_name,
                "subtotal": str(d["subtotal"]),
            },
        )
        return _CREATED(resp_data, request=request)


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

        from apps.payments.domain.exceptions import OrderNotFoundError
        from apps.payments.infrastructure.gateways import get_gateway

        order_repo = _ORDER_REPO()
        try:
            order = order_repo.get_by_id(d["order_id"], user_id=_UUID(str(request.user.id)))
        except OrderNotFoundError:
            return error_response(code="ERR_NOT_FOUND", message="Order not found.", http_status=404, request=request)
        gateway = get_gateway(order.gateway)
        result = _REFUND_UC(
            order_repo=order_repo,
            refund_repo=_REFUND_REPO(),
            gateway=gateway,
        ).execute(
            order_id=d["order_id"],
            user_id=_UUID(str(request.user.id)),
            amount=d["amount"],
            reason=d["reason"],
        )
        publish_audit(
            request=request,
            user_id=_UUID(str(request.user.id)),
            event_type="refund.requested",
            metadata={
                "order_id": str(d["order_id"]),
                "reason": d["reason"],
            },
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
                payload=_order_completed_payload(order),
            )
            publish_audit(
                request=request,
                user_id=_UUID(str(order.user_id)),
                event_type="order.completed",
                metadata={"gateway": "khalti"},
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
                payload=_order_completed_payload(order),
            )
            publish_audit(
                request=request,
                user_id=_UUID(str(order.user_id)),
                event_type="order.completed",
                metadata={"gateway": "esewa"},
            )
        return success_response({"received": True}, request=request)


class StripeWebhookView(APIView):
    """Receive payment status callbacks from Stripe via webhook events."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Webhooks"],
        summary="Stripe payment webhook",
        auth=[],
        responses={200: OpenApiResponse(description="Webhook processed.")},
    )
    def post(self, request: Request) -> Response:
        """Process the Stripe webhook event and update the matching order."""
        sig = request.headers.get("Stripe-Signature", "")
        if not verify_stripe_signature(request.body, sig):
            return error_response(
                code="ERR_PAYMENT_INVALID_SIGNATURE",
                message="Stripe webhook signature verification failed.",
                http_status=400,
                request=request,
            )
        import json

        event_data = json.loads(request.body)
        event_type = event_data.get("type", "")

        # * we only care about checkout.session.completed and checkout.session.expired
        if event_type == "checkout.session.completed":
            session_obj = event_data.get("data", {}).get("object", {})
            session_id = session_obj.get("id", "")
            order = _WEBHOOK_UC(_ORDER_REPO()).execute(
                gateway_order_id=session_id,
                status="completed",
                gateway_transaction_id=session_obj.get("payment_intent", ""),
            )
            if order.status == "completed":
                publish_event(
                    routing_key="payment.order.completed",
                    payload=_order_completed_payload(order),
                )
                publish_audit(
                    request=request,
                    user_id=_UUID(str(order.user_id)),
                    event_type="order.completed",
                    metadata={"gateway": "stripe"},
                )
        elif event_type in ("checkout.session.expired", "checkout.session.async_payment_failed"):
            session_obj = event_data.get("data", {}).get("object", {})
            session_id = session_obj.get("id", "")
            _WEBHOOK_UC(_ORDER_REPO()).execute(
                gateway_order_id=session_id,
                status="failed",
                gateway_transaction_id="",
            )

        return success_response({"received": True}, request=request)


class PayPalWebhookView(APIView):
    """Capture a PayPal order after user approval and process the result."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Webhooks"],
        summary="PayPal payment callback",
        auth=[],
        responses={200: OpenApiResponse(description="Payment captured.")},
    )
    def post(self, request: Request) -> Response:
        """Capture the approved PayPal order and mark it completed or failed."""
        from apps.payments.infrastructure.gateways.paypal import capture_order

        paypal_order_id = request.data.get("paypal_order_id", "")
        if not paypal_order_id:
            return error_response(
                code="ERR_PAYMENT_MISSING_ID",
                message="paypal_order_id is required.",
                http_status=400,
                request=request,
            )

        try:
            capture_response = capture_order(paypal_order_id)
        except Exception as exc:
            return error_response(
                code="ERR_PAYMENT_CAPTURE_FAILED",
                message=str(exc),
                http_status=502,
                request=request,
            )

        capture_status = capture_response.get("status", "")
        internal_status = "completed" if capture_status == "COMPLETED" else "failed"

        order = _WEBHOOK_UC(_ORDER_REPO()).execute(
            gateway_order_id=paypal_order_id,
            status=internal_status,
            gateway_transaction_id=paypal_order_id,
        )
        if order.status == "completed":
            publish_event(
                routing_key="payment.order.completed",
                payload=_order_completed_payload(order),
            )
            publish_audit(
                request=request,
                user_id=_UUID(str(order.user_id)),
                event_type="order.completed",
                metadata={"gateway": "paypal"},
            )
        return success_response(
            {"captured": internal_status == "completed", "order_id": str(order.id)},
            request=request,
        )


class PaymentCallbackView(APIView):
    """Universal callback endpoint - gateways redirect here after payment. Redirects to frontend."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Callbacks"],
        summary="Gateway callback redirect",
        auth=[],
        responses={302: OpenApiResponse(description="Redirect to frontend.")},
    )
    def get(self, request: Request, gateway: str) -> Response:
        """Parse gateway-specific query params and redirect to the frontend success/failure page."""
        from django.http import HttpResponseRedirect

        base = settings.FRONTEND_WEB_URL
        # custom redirect path from the initiating flow (e.g. subscription vs ticket)
        custom_redirect = request.query_params.get("redirect", "")

        if gateway == "khalti":
            # Khalti appends ?pidx=...&status=...&purchase_order_id=...
            status = request.query_params.get("status", "")
            pidx = request.query_params.get("pidx", "")
            if status == "Completed" and pidx:
                # * look up and auto-complete via webhook UC
                try:
                    order = _WEBHOOK_UC(_ORDER_REPO()).execute(
                        gateway_order_id=pidx,
                        status="completed",
                        gateway_transaction_id=request.query_params.get("transaction_id", ""),
                    )
                    if order.status == "completed":
                        publish_event(
                            routing_key="payment.order.completed",
                            payload=_order_completed_payload(order),
                        )
                    success_path = custom_redirect or f"/payment/success?order_id={order.id}"
                    return HttpResponseRedirect(f"{base}{success_path}")
                except Exception:
                    pass
            return HttpResponseRedirect(f"{base}/payment/failure")

        if gateway == "esewa":
            # eSewa appends ?data=<base64_json> on success
            import base64
            import json

            data_b64 = request.query_params.get("data", "")
            if data_b64:
                try:
                    decoded = json.loads(base64.b64decode(data_b64))
                    tx_uuid = decoded.get("transaction_uuid", "")
                    status_val = decoded.get("status", "")
                    internal = "completed" if status_val == "COMPLETE" else "failed"
                    order = _WEBHOOK_UC(_ORDER_REPO()).execute(
                        gateway_order_id=tx_uuid,
                        status=internal,
                        gateway_transaction_id=decoded.get("transaction_code", ""),
                    )
                    if order.status == "completed":
                        publish_event(
                            routing_key="payment.order.completed",
                            payload=_order_completed_payload(order),
                        )
                    success_path = custom_redirect or f"/payment/success?order_id={order.id}"
                    return HttpResponseRedirect(f"{base}{success_path}")
                except Exception:
                    pass
            return HttpResponseRedirect(f"{base}/payment/failure")

        if gateway == "stripe":
            session_id = request.query_params.get("session_id", "")
            if session_id:
                return HttpResponseRedirect(f"{base}/payment/success?session_id={session_id}")
            return HttpResponseRedirect(f"{base}/payment/failure")

        if gateway == "paypal":
            token = request.query_params.get("token", "")
            if token:
                return HttpResponseRedirect(f"{base}/payment/success?paypal_token={token}")
            return HttpResponseRedirect(f"{base}/payment/failure")

        return HttpResponseRedirect(f"{base}/payment/failure")


# * ---- Subscription views ----


class SubscriptionCreateView(APIView):
    """GET /subscriptions/ - list all subscriptions; POST /subscriptions/ - create one."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Subscriptions"],
        summary="List all subscriptions",
        description="Returns all subscriptions. Optionally filter by org_id query parameter.",
        responses={200: OpenApiResponse(description="All subscriptions.", response=SubscriptionResponseSerializer(many=True))},
    )
    def get(self, request: Request) -> Response:
        """Return subscriptions filtered by org_id if provided, otherwise all."""
        from apps.payments.infrastructure.repositories import DjangoSubscriptionRepository

        repo = DjangoSubscriptionRepository()
        org_id_param = request.query_params.get("org_id", "")
        if org_id_param:
            subs = repo.list_by_org(_UUID(org_id_param))
        else:
            subs = repo.list_all()
        return success_response(SubscriptionResponseSerializer(subs, many=True).data, request=request)

    @extend_schema(
        tags=["Subscriptions"],
        summary="Subscribe to a plan",
        request=CreateSubscriptionSerializer,
        responses={
            201: OpenApiResponse(description="Subscription created."),
            409: OpenApiResponse(description="Active subscription already exists."),
        },
    )
    def post(self, request: Request) -> Response:
        """Create a subscription and return the payment URL for paid plans."""
        from apps.payments.application.use_cases.create_subscription import CreateSubscriptionUseCase
        from apps.payments.infrastructure.repositories import DjangoSubscriptionRepository

        ser = CreateSubscriptionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        gateway_name = d["gateway"]
        email = request.user.token.get("email", "")
        callback_base = settings.PAYMENT_CALLBACK_BASE_URL
        base_web = settings.FRONTEND_WEB_URL

        gateway_client = get_gateway(gateway_name)

        sub, session = CreateSubscriptionUseCase(
            sub_repo=DjangoSubscriptionRepository(),
            gateway_client=gateway_client,
        ).execute(
            org_id=d["org_id"],
            plan=d["plan"],
            gateway=gateway_name,
            return_url=f"{callback_base}/callbacks/{gateway_name}/?redirect=/org/pricing?subscribed=true",
            cancel_url=f"{base_web}/org/pricing?cancelled=true",
            customer_email=email,
        )

        resp_data = SubscriptionResponseSerializer(sub).data
        if session is not None:
            resp_data["payment_url"] = session.payment_url
            if gateway_name == "esewa" and "form_data" in session.raw_response:
                resp_data["esewa_form_data"] = session.raw_response["form_data"]
                resp_data["esewa_form_url"] = session.raw_response["form_url"]
        publish_audit(
            request=request,
            user_id=_UUID(str(request.user.id)),
            event_type="subscription.created",
            metadata={
                "org_id": str(d["org_id"]),
                "plan": d["plan"],
            },
        )
        return _CREATED(resp_data, request=request)


class SubscriptionCurrentView(APIView):
    """GET /subscriptions/current/?org_id=... - get active subscription for an org."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Subscriptions"],
        summary="Get active subscription",
        responses={
            200: OpenApiResponse(description="Active subscription found."),
            404: OpenApiResponse(description="No active subscription."),
        },
    )
    def get(self, request: Request) -> Response:
        """Return the org's active subscription or 404."""
        from apps.payments.infrastructure.repositories import DjangoSubscriptionRepository

        org_id = request.query_params.get("org_id", "")
        if not org_id:
            return error_response(
                code="ERR_PAYMENT_MISSING_ORG_ID",
                message="org_id query parameter is required.",
                http_status=400,
                request=request,
            )

        sub = DjangoSubscriptionRepository().get_active_by_org(_UUID(org_id))
        if sub is None:
            return success_response(None, request=request)
        return success_response(SubscriptionResponseSerializer(sub).data, request=request)


class SubscriptionCancelView(APIView):
    """POST /subscriptions/cancel/ - cancel the org's active subscription."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Subscriptions"],
        summary="Cancel subscription",
        responses={
            200: OpenApiResponse(description="Subscription cancelled."),
            404: OpenApiResponse(description="No active subscription."),
        },
    )
    def post(self, request: Request) -> Response:
        """Cancel the active subscription for the given org."""
        from apps.payments.application.use_cases.cancel_subscription import CancelSubscriptionUseCase
        from apps.payments.infrastructure.repositories import DjangoSubscriptionRepository

        ser = CancelSubscriptionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        sub = CancelSubscriptionUseCase(
            sub_repo=DjangoSubscriptionRepository(),
        ).execute(org_id=ser.validated_data["org_id"])

        publish_audit(
            request=request,
            user_id=_UUID(str(request.user.id)),
            event_type="subscription.cancelled",
            metadata={
                "org_id": str(ser.validated_data["org_id"]),
            },
        )
        return success_response(SubscriptionResponseSerializer(sub).data, request=request)


class SubscriptionPaymentHistoryView(APIView):
    """GET /subscriptions/<uuid>/payments/ - billing history for a subscription."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Subscriptions"],
        summary="Subscription payment history",
        responses={200: OpenApiResponse(description="Payment records.")},
    )
    def get(self, request: Request, subscription_id: uuid.UUID) -> Response:
        """Return all payment records for a subscription."""
        from apps.payments.infrastructure.repositories import DjangoSubscriptionPaymentRepository

        payments = DjangoSubscriptionPaymentRepository().list_by_subscription(subscription_id)
        return success_response(
            SubscriptionPaymentResponseSerializer(payments, many=True).data,
            request=request,
        )


class PromoCodeListCreateView(APIView):
    """GET /promo-codes/ - list; POST /promo-codes/ - create."""

    permission_classes = [IsAuthenticated]

    def get_permissions(self) -> list:
        """GET is open to any authenticated user; POST requires org admin role."""
        if self.request.method == "POST":
            return [IsOrgAdmin()]
        return [IsAuthenticated()]

    @extend_schema(
        tags=["Promo Codes"],
        summary="List promo codes",
        responses={200: PromoCodeResponseSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        """Return all promo codes."""
        promos = _LIST_PROMOS_UC(_PROMO_REPO()).execute()
        return success_response(PromoCodeResponseSerializer(promos, many=True).data, request=request)

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
        publish_audit(
            request=request,
            user_id=_UUID(str(request.user.id)),
            event_type="promo.created",
            metadata={
                "code": d["code"],
            },
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

    # * org admin required for both listing and creating disputes
    permission_classes = [IsOrgAdmin]

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
        return success_response(DisputeResponseSerializer(disputes, many=True).data, request=request)

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
        publish_audit(
            request=request,
            user_id=_UUID(str(request.user.id)),
            event_type="dispute.created",
            metadata={
                "reason": d["reason"],
            },
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
            return error_response(code=exc.code, message=str(exc), http_status=404, request=request)
        publish_audit(
            request=request,
            user_id=_UUID(str(request.user.id)),
            event_type="dispute.updated",
            metadata={
                "status": d["status"],
            },
        )
        return success_response(DisputeResponseSerializer(dispute).data, request=request)


class DisputeListAllView(APIView):
    """GET /disputes/ - list all disputes platform-wide (admin)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Disputes"],
        summary="List all disputes (admin)",
        responses={200: DisputeResponseSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        """Return every dispute across all orders, newest first."""
        disputes = _DISPUTE_REPO().list_all()
        return success_response(DisputeResponseSerializer(disputes, many=True).data, request=request)


class AdminOrderListView(APIView):
    """GET /admin/orders/ - list all platform orders (superadmin only)."""

    permission_classes = [IsSuperAdminFromAllowedIP]

    @extend_schema(
        tags=["Admin"],
        summary="List all orders (admin)",
        description="Returns every payment order across all users, newest first. Requires superadmin access.",
        responses={
            200: OpenApiResponse(description="All platform orders.", response=_ORDER_RESP_SER(many=True)),
            401: OpenApiResponse(description="Missing or invalid JWT."),
            403: OpenApiResponse(description="Not a superadmin or IP not allowed."),
        },
    )
    def get(self, request: Request) -> Response:
        """Return every order across all users, not scoped to the requester."""
        results = _ORDER_REPO().list_all()
        return success_response(_ORDER_RESP_SER(results, many=True).data, request=request)


class ConnectedAccountView(APIView):
    """POST /connect/accounts/ - register a Stripe Connect account for an org."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Stripe Connect"],
        summary="Register Stripe Connect account",
        description="Creates a Stripe Express account for the org and returns an onboarding URL.",
        responses={
            201: OpenApiResponse(description="Account created."),
            502: OpenApiResponse(description="Stripe error."),
        },
    )
    def post(self, request: Request) -> Response:
        """Create a Stripe Connect account and return the onboarding URL."""
        from rest_framework import serializers as drf_serializers

        from apps.payments.infrastructure.gateways.stripe_connect import StripeConnectGateway

        class ConnectSerializer(drf_serializers.Serializer):
            org_id = drf_serializers.UUIDField()
            return_url = drf_serializers.URLField()
            refresh_url = drf_serializers.URLField()

        ser = ConnectSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        entity = CreateConnectedAccountUseCase(DjangoConnectedAccountRepository(), StripeConnectGateway()).execute(
            org_id=d["org_id"],
            return_url=d["return_url"],
            refresh_url=d["refresh_url"],
        )
        return created_response(
            {
                "id": str(entity.id),
                "org_id": str(entity.org_id),
                "stripe_account_id": entity.stripe_account_id,
                "onboarding_url": entity.onboarding_url,
            },
            request=request,
        )


class PayoutCreateView(APIView):
    """POST /connect/payouts/ - transfer proceeds to a connected Stripe account."""

    # * only org owners can trigger payouts
    permission_classes = [IsOrgOwner]

    @extend_schema(
        tags=["Stripe Connect"],
        summary="Create payout",
        description="Transfer funds to the org's connected Stripe account.",
        responses={
            201: OpenApiResponse(description="Payout created."),
            404: OpenApiResponse(description="No connected account found."),
            502: OpenApiResponse(description="Stripe transfer failed."),
        },
    )
    def post(self, request: Request) -> Response:
        """Validate payload and trigger the Stripe transfer."""
        from decimal import Decimal

        from rest_framework import serializers as drf_serializers

        from apps.payments.infrastructure.gateways.stripe_connect import StripeConnectGateway

        class PayoutSerializer(drf_serializers.Serializer):
            org_id = drf_serializers.UUIDField()
            amount = drf_serializers.DecimalField(max_digits=12, decimal_places=2)
            currency = drf_serializers.CharField(max_length=10, default="USD")
            description = drf_serializers.CharField(max_length=500, default="")

        ser = PayoutSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        entity = CreatePayoutUseCase(
            DjangoConnectedAccountRepository(),
            DjangoPayoutRepository(),
            StripeConnectGateway(),
        ).execute(
            org_id=d["org_id"],
            amount=Decimal(str(d["amount"])),
            currency=d["currency"],
            description=d["description"],
        )
        return created_response(
            {
                "id": str(entity.id),
                "org_id": str(entity.org_id),
                "stripe_transfer_id": entity.stripe_transfer_id,
                "amount": str(entity.amount),
                "currency": entity.currency,
            },
            request=request,
        )
