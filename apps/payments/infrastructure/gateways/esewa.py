"""eSewa e-payment gateway integration (V2 form-based flow)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import uuid
from decimal import Decimal

from django.conf import settings

from apps.payments.domain.exceptions import PaymentGatewayError
from apps.payments.domain.gateway import IPaymentGateway, PaymentSession
from apps.payments.infrastructure.gateways.retry import with_retry

logger = logging.getLogger(__name__)

_SANDBOX_URL = "https://rc-epay.esewa.com.np/api/epay/main/v2/form"
_LIVE_URL = "https://epay.esewa.com.np/api/epay/main/v2/form"


def _sign(message: str, secret: str) -> str:
    """Generate HMAC-SHA256 signature encoded as base64 for eSewa form signing."""
    sig = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(sig).decode("utf-8")


class EsewaGateway(IPaymentGateway):
    """eSewa V2; builds a signed form payload. Client submits the form to eSewa's URL."""

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
        Build signed eSewa form data. Client POSTs this form to eSewa to start payment.

        eSewa uses a form-redirect model; the backend builds the signed payload,
        the frontend submits it as a form POST to eSewa's payment URL.

        @returns PaymentSession with transaction_uuid as gateway_order_id,
                 the form action URL as payment_url, and signed form fields in raw_response
        @raises PaymentGatewayError if configuration is missing
        """
        secret = getattr(settings, "ESEWA_SECRET_KEY", "")
        product_code = getattr(settings, "ESEWA_PRODUCT_CODE", "EPAYTEST")

        if not secret:
            raise PaymentGatewayError("ESEWA_SECRET_KEY is not configured.")

        form_url = _SANDBOX_URL if getattr(settings, "ESEWA_SANDBOX", True) else _LIVE_URL

        # ! eSewa expects amount as a string with no decimal places for NPR
        total_amount = str(int(amount))
        transaction_uuid = str(uuid.uuid4())

        # * signed fields must be in exact order: total_amount, transaction_uuid, product_code
        signed_field_names = "total_amount,transaction_uuid,product_code"
        message = f"total_amount={total_amount},transaction_uuid={transaction_uuid},product_code={product_code}"
        signature = _sign(message, secret)

        form_data = {
            "amount": total_amount,
            "tax_amount": "0",
            "total_amount": total_amount,
            "transaction_uuid": transaction_uuid,
            "product_code": product_code,
            "product_service_charge": "0",
            "product_delivery_charge": "0",
            "success_url": return_url,
            "failure_url": cancel_url,
            "signed_field_names": signed_field_names,
            "signature": signature,
        }

        return PaymentSession(
            gateway_order_id=transaction_uuid,
            payment_url=form_url,
            raw_response={"form_data": form_data, "form_url": form_url},
        )

    def refund(self, *, gateway_order_id: str, amount: Decimal) -> str:
        """eSewa does not support programmatic refunds via API; raise to signal manual handling."""
        raise PaymentGatewayError("eSewa does not support automated refunds; process manually in the eSewa merchant dashboard.")
