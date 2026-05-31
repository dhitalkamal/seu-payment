"""Exception handler and base domain error class."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


class DomainError(Exception):
    """Base for all domain-level errors.

    Subclasses define `code` using ERR_<CONTEXT>_<REASON> format
    and `http_status` for the correct HTTP response code.
    """

    http_status: int = 400
    code: str = "ERR_DOMAIN_ERROR"

    def __init__(self, detail: str) -> None:
        """Store the human-readable problem detail."""
        self.detail = detail
        super().__init__(detail)


def _meta(request: Any = None) -> dict:
    """Build the standard meta block (duplicated here to avoid circular imports)."""
    request_id = getattr(request, "request_id", None) or str(uuid.uuid4())
    return {
        "request_id": request_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _body(code: str, message: str, details: Any, request: Any) -> dict:
    """Assemble the error envelope."""
    return {
        "data": None,
        "error": {"code": code, "message": message, "details": details},
        "meta": _meta(request),
    }


def _extract(data: dict | list | str, fallback: str) -> str:
    """Pull a readable string from whatever DRF puts in response.data."""
    if isinstance(data, dict):
        return str(data.get("detail", fallback))
    if isinstance(data, list) and data:
        return str(data[0])
    return str(data) if data else fallback


def api_exception_handler(exc: Exception, context: dict) -> Response | None:
    """Convert DRF and domain exceptions into the standard error envelope."""
    request = context.get("request")

    if isinstance(exc, DomainError):
        return Response(_body(exc.code, exc.detail, None, request), status=exc.http_status)

    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    data = response.data
    http_status = response.status_code

    if http_status == status.HTTP_400_BAD_REQUEST:
        return Response(
            _body("ERR_VALIDATION_FAILED", "The submitted data failed validation.", data, request),
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    if http_status == status.HTTP_401_UNAUTHORIZED:
        msg = _extract(data, "Authentication credentials were not provided.")
        return Response(_body("ERR_AUTH_UNAUTHORIZED", msg, None, request), status=401)
    if http_status == status.HTTP_403_FORBIDDEN:
        msg = _extract(data, "You do not have permission to perform this action.")
        return Response(_body("ERR_PERMISSION_DENIED", msg, None, request), status=403)
    if http_status == status.HTTP_404_NOT_FOUND:
        msg = _extract(data, "The requested resource was not found.")
        return Response(_body("ERR_RESOURCE_NOT_FOUND", msg, None, request), status=404)
    if http_status == status.HTTP_405_METHOD_NOT_ALLOWED:
        msg = _extract(data, "Method not allowed.")
        return Response(_body("ERR_METHOD_NOT_ALLOWED", msg, None, request), status=405)
    if http_status == status.HTTP_429_TOO_MANY_REQUESTS:
        msg = _extract(data, "Request was throttled.")
        return Response(_body("ERR_RATE_LIMIT_EXCEEDED", msg, None, request), status=429)
    return Response(
        _body("ERR_INTERNAL_ERROR", _extract(data, "An unexpected error occurred."), None, request),
        status=http_status,
    )
