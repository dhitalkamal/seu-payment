"""HMAC signature verification for payment gateway webhooks."""

from __future__ import annotations

import hashlib
import hmac
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def verify_khalti_signature(payload_bytes: bytes, received_signature: str) -> bool:
    """
    Verify a Khalti webhook payload against the configured HMAC secret.

    Khalti signs the raw request body with HMAC-SHA256 using the merchant secret.
    Returns True if the signature matches or if no secret is configured (dev mode).
    """
    secret = settings.KHALTI_WEBHOOK_SECRET
    if not secret:
        logger.warning("KHALTI_WEBHOOK_SECRET not set — skipping signature check (dev mode).")
        return True
    expected = hmac.new(
        secret.encode("utf-8"), payload_bytes, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, received_signature)


def verify_esewa_signature(payload_bytes: bytes, received_signature: str) -> bool:
    """
    Verify an eSewa webhook payload against the configured HMAC secret.

    eSewa signs the raw request body with HMAC-SHA256.
    Returns True if the signature matches or if no secret is configured (dev mode).
    """
    secret = settings.ESEWA_WEBHOOK_SECRET
    if not secret:
        logger.warning("ESEWA_WEBHOOK_SECRET not set — skipping signature check (dev mode).")
        return True
    expected = hmac.new(
        secret.encode("utf-8"), payload_bytes, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, received_signature)
