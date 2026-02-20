"""Stripe Checkout Session gateway integration."""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings

from apps.payments.domain.exceptions import PaymentGatewayError
from apps.payments.domain.gateway import IPaymentGateway, PaymentSession
from apps.payments.infrastructure.gateways.retry import with_retry

logger = logging.getLogger(__name__)

_API_URL = "https://api.stripe.com/v1/checkout/sessions"
_REFUNDS_URL = "https://api.stripe.com/v1/refunds"


class StripeGateway(IPaymentGateway):
    """Stripe Checkout; creates a hosted session and returns the payment URL."""

    @with_retry(max_attempts=3, base_delay=1.0)
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
        Create a Stripe Checkout Session via the REST API (no SDK needed).

        @returns PaymentSession with session.id as gateway_order_id and session.url as payment_url
        @raises PaymentGatewayError if Stripe rejects or is unreachable
        """
        secret = settings.STRIPE_SECRET_KEY
        if not secret:
            raise PaymentGatewayError("STRIPE_SECRET_KEY is not configured.")

        # ! Stripe expects amount in smallest currency unit; NPR has no subunit so 1:1,
        # but USD/EUR need cents. We use paisa for NPR (100 paisa = 1 NPR).
        stripe_currency = currency.lower()
        if stripe_currency in ("npr", "usd", "eur", "gbp"):
            amount_minor = int(amount * 100)
        else:
            amount_minor = int(amount)

        # * Stripe REST API uses form-encoded params
        import urllib.parse

        params = urllib.parse.urlencode(
            [
                ("payment_method_types[]", "card"),
                ("mode", "payment"),
                ("success_url", f"{return_url}?session_id={{CHECKOUT_SESSION_ID}}"),
                ("cancel_url", cancel_url),
                ("customer_email", customer_email),
                ("client_reference_id", order_id),
                ("line_items[0][price_data][currency]", stripe_currency),
                ("line_items[0][price_data][product_data][name]", description[:256]),
                ("line_items[0][price_data][unit_amount]", str(amount_minor)),
                ("line_items[0][quantity]", "1"),
                ("metadata[order_id]", order_id),
            ]
        ).encode("utf-8")

        req = Request(
            _API_URL,
            data=params,
            headers={
                "Authorization": f"Bearer {secret}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )

        try:
            with urlopen(req, timeout=15) as resp:
                body = json.loads(resp.read())
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            logger.error("Stripe create session failed: %s -- %s", exc, error_body)
            raise PaymentGatewayError(f"Stripe session creation failed: {exc}") from exc
        except (URLError, TimeoutError) as exc:
            logger.error("Stripe unreachable: %s", exc)
            raise PaymentGatewayError(f"Stripe unreachable: {exc}") from exc

        session_id = body.get("id", "")
        session_url = body.get("url", "")

        if not session_id or not session_url:
            logger.error("Stripe returned unexpected response: %s", body)
            raise PaymentGatewayError("Stripe returned an invalid response; missing id or url.")

        return PaymentSession(
            gateway_order_id=session_id,
            payment_url=session_url,
            raw_response=body,
        )

    @with_retry(max_attempts=3, base_delay=1.0)
    def refund(self, *, gateway_order_id: str, amount: Decimal) -> str:
        """
        Issue a refund against a Stripe Checkout Session.

        Looks up the PaymentIntent from the session, then creates a refund.

        @param gateway_order_id - the Stripe session ID (cs_...)
        @param amount - amount to refund in the order's currency
        @returns the Stripe refund ID (re_...)
        @raises PaymentGatewayError on network or API failure
        """
        import urllib.parse

        secret = settings.STRIPE_SECRET_KEY
        if not secret:
            raise PaymentGatewayError("STRIPE_SECRET_KEY is not configured.")

        # * first retrieve the session to get the payment_intent ID
        session_req = Request(
            f"{_API_URL}/{gateway_order_id}",
            headers={"Authorization": f"Bearer {secret}"},
            method="GET",
        )
        try:
            with urlopen(session_req, timeout=15) as resp:
                session_body = json.loads(resp.read())
        except (HTTPError, URLError, TimeoutError) as exc:
            raise PaymentGatewayError(f"Stripe session lookup failed: {exc}") from exc

        payment_intent = session_body.get("payment_intent", "")
        if not payment_intent:
            raise PaymentGatewayError("Stripe session has no payment_intent; cannot refund.")

        amount_minor = int(amount * 100)
        refund_params = urllib.parse.urlencode([("payment_intent", payment_intent), ("amount", str(amount_minor))]).encode("utf-8")

        refund_req = Request(
            _REFUNDS_URL,
            data=refund_params,
            headers={
                "Authorization": f"Bearer {secret}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )

        try:
            with urlopen(refund_req, timeout=15) as resp:
                refund_body = json.loads(resp.read())
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            logger.error("Stripe refund failed: %s -- %s", exc, error_body)
            raise PaymentGatewayError(f"Stripe refund failed: {exc}") from exc
        except (URLError, TimeoutError) as exc:
            logger.error("Stripe refund unreachable: %s", exc)
            raise PaymentGatewayError(f"Stripe refund unreachable: {exc}") from exc

        refund_id = refund_body.get("id", "")
        if not refund_id:
            raise PaymentGatewayError("Stripe refund returned no ID.")

        return refund_id
