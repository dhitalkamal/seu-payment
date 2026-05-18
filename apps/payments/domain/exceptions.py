"""Domain errors raised by payments use cases and never swallowed silently."""

from __future__ import annotations

from apps.common.api.exceptions import DomainError


class OrderNotFoundError(DomainError):
    """No order matches the given identifier or the requesting user does not own it."""

    http_status = 404
    code = "ERR_PAYMENT_ORDER_NOT_FOUND"


class OrderAlreadyExistsError(DomainError):
    """An order already exists for this registration."""

    http_status = 409
    code = "ERR_PAYMENT_ORDER_ALREADY_EXISTS"


class InvalidPromoCodeError(DomainError):
    """The promo code is missing, expired, inactive, or exhausted."""

    http_status = 422
    code = "ERR_PAYMENT_INVALID_PROMO_CODE"


class PaymentGatewayError(DomainError):
    """The payment gateway returned an unexpected error."""

    http_status = 502
    code = "ERR_PAYMENT_GATEWAY_ERROR"


class RefundNotAllowedError(DomainError):
    """The order cannot be refunded in its current status."""

    http_status = 422
    code = "ERR_PAYMENT_REFUND_NOT_ALLOWED"


class DisputeNotFoundError(DomainError):
    """No dispute matches the given identifier."""

    http_status = 404
    code = "ERR_PAYMENT_DISPUTE_NOT_FOUND"
