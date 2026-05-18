"""HMAC/signature verification for payment gateway webhooks."""

from __future__ import annotations

import hashlib
import hmac
import logging
import time

from django.conf import settings

logger = logging.getLogger(__name__)


def verify_khalti_signature(payload_bytes: bytes, received_signature: str) -> bool:
    """
    Verify a Khalti webhook payload against the configured HMAC secret.

    Khalti signs the raw request body with HMAC-SHA256 using the merchant secret.
    Returns True if the signature matches or if no secret is configured (dev mode).
    """
    secret = getattr(settings, "KHALTI_WEBHOOK_SECRET", "")
    if not secret:
        logger.warning("KHALTI_WEBHOOK_SECRET not set — skipping signature check (dev mode).")
        return True
    expected = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received_signature)


def verify_esewa_signature(payload_bytes: bytes, received_signature: str) -> bool:
    """
    Verify an eSewa webhook payload against the configured HMAC secret.

    eSewa signs the raw request body with HMAC-SHA256.
    Returns True if the signature matches or if no secret is configured (dev mode).
    """
    secret = getattr(settings, "ESEWA_WEBHOOK_SECRET", "")
    if not secret:
        logger.warning("ESEWA_WEBHOOK_SECRET not set — skipping signature check (dev mode).")
        return True
    expected = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received_signature)


def verify_stripe_signature(payload_bytes: bytes, sig_header: str) -> bool:
    """
    Verify a Stripe webhook event using the Stripe-Signature header.

    Stripe uses a scheme like: t=<timestamp>,v1=<hmac_sha256>
    We validate the v1 signature against our webhook secret.
    Returns True if valid or if no secret is configured (dev mode).
    """
    secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")
    if not secret:
        logger.warning("STRIPE_WEBHOOK_SECRET not set — skipping signature check (dev mode).")
        return True

    # * parse the Stripe-Signature header
    elements = dict(pair.split("=", 1) for pair in sig_header.split(",") if "=" in pair)
    timestamp = elements.get("t", "")
    received_sig = elements.get("v1", "")

    if not timestamp or not received_sig:
        logger.warning("Stripe signature header missing t or v1 fields.")
        return False

    # ! reject signatures older than 5 minutes to prevent replay attacks
    try:
        if abs(time.time() - int(timestamp)) > 300:
            logger.warning("Stripe webhook timestamp too old — possible replay.")
            return False
    except ValueError:
        return False

    # * signed payload is "{timestamp}.{body}"
    signed_payload = f"{timestamp}.{payload_bytes.decode('utf-8')}"
    expected = hmac.new(
        secret.encode("utf-8"),
        signed_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, received_sig)
