"""PayPal Checkout Orders V2 gateway integration."""

from __future__ import annotations

import base64
import json
import logging
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings

from apps.payments.domain.exceptions import PaymentGatewayError
from apps.payments.domain.gateway import IPaymentGateway, PaymentSession

logger = logging.getLogger(__name__)

_SANDBOX_API = "https://api-m.sandbox.paypal.com"
_LIVE_API = "https://api-m.paypal.com"


def _get_access_token(base_url: str, client_id: str, client_secret: str) -> str:
    """Exchange client credentials for a PayPal bearer token."""
    creds = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    req = Request(
        f"{base_url}/v1/oauth2/token",
        data=b"grant_type=client_credentials",
        headers={
            "Authorization": f"Basic {creds}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read())
        return body["access_token"]
    except (HTTPError, URLError, KeyError, TimeoutError) as exc:
        raise PaymentGatewayError(f"PayPal auth failed: {exc}") from exc


class PayPalGateway(IPaymentGateway):
    """PayPal Orders V2 — creates an order and returns the approval URL."""

    def initiate(
        self,
        *,
        order_id: str,
        amount: Decimal,
        currency: str,
        description: str,
        customer_email: str,
        return_url: str,
        cancel_url: str,
    ) -> PaymentSession:
        """
        Create a PayPal order and extract the approval link.

        @returns PaymentSession with PayPal order.id as gateway_order_id and approval URL
        @raises PaymentGatewayError on auth failure, network error, or invalid response
        """
        client_id = settings.PAYPAL_CLIENT_ID
        client_secret = settings.PAYPAL_CLIENT_SECRET
        if not client_id or not client_secret:
            raise PaymentGatewayError("PayPal credentials not configured.")

        base_url = _SANDBOX_API if getattr(settings, "PAYPAL_SANDBOX", True) else _LIVE_API
        token = _get_access_token(base_url, client_id, client_secret)

        # ! PayPal amount must be a string with exactly 2 decimal places
        amount_str = f"{amount:.2f}"

        payload = json.dumps(
            {
                "intent": "CAPTURE",
                "purchase_units": [
                    {
                        "reference_id": order_id,
                        "description": description[:127],
                        "amount": {
                            "currency_code": currency.upper(),
                            "value": amount_str,
                        },
                    }
                ],
                "payment_source": {
                    "paypal": {
                        "experience_context": {
                            "return_url": return_url,
                            "cancel_url": cancel_url,
                            "brand_name": "Sansaar",
                            "user_action": "PAY_NOW",
                            "landing_page": "LOGIN",
                        }
                    }
                },
            }
        ).encode("utf-8")

        req = Request(
            f"{base_url}/v2/checkout/orders",
            data=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
            method="POST",
        )

        try:
            with urlopen(req, timeout=15) as resp:
                body = json.loads(resp.read())
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            logger.error("PayPal create order failed: %s — %s", exc, error_body)
            raise PaymentGatewayError(f"PayPal order creation failed: {exc}") from exc
        except (URLError, TimeoutError) as exc:
            logger.error("PayPal unreachable: %s", exc)
            raise PaymentGatewayError(f"PayPal unreachable: {exc}") from exc

        paypal_order_id = body.get("id", "")

        # * extract the "payer-action" or "approve" link from the HATEOAS links
        approval_url = ""
        for link in body.get("links", []):
            if link.get("rel") in ("payer-action", "approve"):
                approval_url = link["href"]
                break

        if not paypal_order_id or not approval_url:
            logger.error("PayPal returned unexpected response: %s", body)
            raise PaymentGatewayError("PayPal returned an invalid response — missing order ID or approval URL.")

        return PaymentSession(
            gateway_order_id=paypal_order_id,
            payment_url=approval_url,
            raw_response=body,
        )


def capture_order(paypal_order_id: str) -> dict:
    """Capture a previously approved PayPal order — called after user approves on PayPal.

    @param paypal_order_id - the PayPal order ID from the approval callback
    @returns the full capture response from PayPal
    @raises PaymentGatewayError on failure
    """
    client_id = settings.PAYPAL_CLIENT_ID
    client_secret = settings.PAYPAL_CLIENT_SECRET
    base_url = _SANDBOX_API if getattr(settings, "PAYPAL_SANDBOX", True) else _LIVE_API
    token = _get_access_token(base_url, client_id, client_secret)

    req = Request(
        f"{base_url}/v2/checkout/orders/{paypal_order_id}/capture",
        data=b"",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except (HTTPError, URLError, TimeoutError) as exc:
        logger.error("PayPal capture failed: %s", exc)
        raise PaymentGatewayError(f"PayPal capture failed: {exc}") from exc
