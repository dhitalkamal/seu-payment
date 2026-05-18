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

logger = logging.getLogger(__name__)

_API_URL = "https://api.stripe.com/v1/checkout/sessions"


class StripeGateway(IPaymentGateway):
    """Stripe Checkout — creates a hosted session and returns the payment URL."""

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

        # ! Stripe expects amount in smallest currency unit — NPR has no subunit so 1:1,
        # but USD/EUR need cents. We use paisa for NPR (100 paisa = 1 NPR).
        stripe_currency = currency.lower()
        if stripe_currency == "npr":
            amount_minor = int(amount * 100)
        elif stripe_currency in ("usd", "eur", "gbp"):
            amount_minor = int(amount * 100)
        else:
            amount_minor = int(amount)

        # * Stripe REST API uses form-encoded params
        import urllib.parse

        params = urllib.parse.urlencode([
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
        ]).encode("utf-8")

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
            logger.error("Stripe create session failed: %s — %s", exc, error_body)
            raise PaymentGatewayError(f"Stripe session creation failed: {exc}") from exc
        except (URLError, TimeoutError) as exc:
            logger.error("Stripe unreachable: %s", exc)
            raise PaymentGatewayError(f"Stripe unreachable: {exc}") from exc

        session_id = body.get("id", "")
        session_url = body.get("url", "")

        if not session_id or not session_url:
            logger.error("Stripe returned unexpected response: %s", body)
            raise PaymentGatewayError("Stripe returned an invalid response — missing id or url.")

        return PaymentSession(
            gateway_order_id=session_id,
            payment_url=session_url,
            raw_response=body,
        )
