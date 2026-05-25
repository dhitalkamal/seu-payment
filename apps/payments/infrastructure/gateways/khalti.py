"""Khalti V2 e-payment gateway integration."""

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

# ! Khalti expects amount in paisa (1 NPR = 100 paisa)
_PAISA_MULTIPLIER = 100

_SANDBOX_URL = "https://a.khalti.com/api/v2/epayment/initiate/"
_LIVE_URL = "https://khalti.com/api/v2/epayment/initiate/"


class KhaltiGateway(IPaymentGateway):
    """Khalti V2 e-payment — initiates a hosted checkout and returns the payment URL."""

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
        Call Khalti's epayment/initiate endpoint.

        @returns PaymentSession with pidx as gateway_order_id and payment_url
        @raises PaymentGatewayError if Khalti rejects or is unreachable
        """
        api_url = _SANDBOX_URL if getattr(settings, "KHALTI_SANDBOX", True) else _LIVE_URL
        secret = settings.KHALTI_SECRET_KEY

        # ! amount must be integer paisa — Khalti rejects decimals
        amount_paisa = int(amount * _PAISA_MULTIPLIER)

        payload = json.dumps(
            {
                "return_url": return_url,
                "website_url": settings.KHALTI_WEBSITE_URL,
                "amount": amount_paisa,
                "purchase_order_id": order_id,
                "purchase_order_name": description[:256],
                "customer_info": {"email": customer_email},
            }
        ).encode("utf-8")

        req = Request(
            api_url,
            data=payload,
            headers={
                "Authorization": f"key {secret}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(req, timeout=15) as resp:
                body = json.loads(resp.read())
        except (HTTPError, URLError, TimeoutError) as exc:
            logger.error("Khalti initiate failed: %s", exc)
            raise PaymentGatewayError(f"Khalti payment initiation failed: {exc}") from exc

        pidx = body.get("pidx", "")
        payment_url = body.get("payment_url", "")

        if not pidx or not payment_url:
            logger.error("Khalti returned unexpected response: %s", body)
            raise PaymentGatewayError("Khalti returned an invalid response — missing pidx or payment_url.")

        return PaymentSession(
            gateway_order_id=pidx,
            payment_url=payment_url,
            raw_response=body,
        )
