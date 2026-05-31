"""Tests for HMAC/signature verification helpers in webhook_verify."""

from __future__ import annotations

import hashlib
import hmac
import time

from apps.payments.infrastructure.webhook_verify import (
    verify_esewa_signature,
    verify_khalti_signature,
    verify_stripe_signature,
)

# -- khalti --


def test_verify_khalti_signature_no_secret_returns_true(settings):
    """When KHALTI_WEBHOOK_SECRET is absent, skip check and return True."""
    settings.KHALTI_WEBHOOK_SECRET = ""
    result = verify_khalti_signature(b"payload", "anysig")
    assert result is True


def test_verify_khalti_signature_valid(settings):
    """Valid HMAC-SHA256 signature passes."""
    secret = "test-secret"
    settings.KHALTI_WEBHOOK_SECRET = secret
    payload = b"some payload"
    sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    assert verify_khalti_signature(payload, sig) is True


def test_verify_khalti_signature_invalid(settings):
    """Wrong signature is rejected."""
    settings.KHALTI_WEBHOOK_SECRET = "test-secret"
    assert verify_khalti_signature(b"some payload", "badsig") is False


# -- esewa --


def test_verify_esewa_signature_no_secret_returns_true(settings):
    """When ESEWA_WEBHOOK_SECRET is absent, skip check and return True."""
    settings.ESEWA_WEBHOOK_SECRET = ""
    result = verify_esewa_signature(b"payload", "anysig")
    assert result is True


def test_verify_esewa_signature_valid(settings):
    """Valid HMAC-SHA256 signature passes."""
    secret = "esewa-secret"
    settings.ESEWA_WEBHOOK_SECRET = secret
    payload = b"esewa body"
    sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    assert verify_esewa_signature(payload, sig) is True


def test_verify_esewa_signature_invalid(settings):
    """Wrong signature is rejected."""
    settings.ESEWA_WEBHOOK_SECRET = "esewa-secret"
    assert verify_esewa_signature(b"esewa body", "badsig") is False


# -- stripe --


def test_verify_stripe_signature_no_secret_returns_true(settings):
    """When STRIPE_WEBHOOK_SECRET is absent, skip check and return True."""
    settings.STRIPE_WEBHOOK_SECRET = ""
    result = verify_stripe_signature(b"payload", "t=1,v1=abc")
    assert result is True


def test_verify_stripe_signature_placeholder_returns_true(settings):
    """When STRIPE_WEBHOOK_SECRET is the placeholder, skip check and return True."""
    settings.STRIPE_WEBHOOK_SECRET = "whsec_CHANGE_ME_IN_PRODUCTION"
    result = verify_stripe_signature(b"payload", "t=1,v1=abc")
    assert result is True


def test_verify_stripe_signature_missing_header_fields(settings):
    """Header missing t or v1 fields returns False."""
    settings.STRIPE_WEBHOOK_SECRET = "whsec_real"
    assert verify_stripe_signature(b"payload", "v1=abc") is False
    assert verify_stripe_signature(b"payload", "t=123") is False


def test_verify_stripe_signature_expired_timestamp(settings):
    """Timestamp older than 5 minutes returns False."""
    settings.STRIPE_WEBHOOK_SECRET = "whsec_real"
    old_ts = str(int(time.time()) - 400)
    assert verify_stripe_signature(b"payload", f"t={old_ts},v1=abc") is False


def test_verify_stripe_signature_valid(settings):
    """Valid Stripe signature passes."""
    secret = "whsec_real"
    settings.STRIPE_WEBHOOK_SECRET = secret
    payload = b"stripe body"
    ts = str(int(time.time()))
    signed = f"{ts}.{payload.decode()}"
    sig = hmac.new(secret.encode(), signed.encode(), hashlib.sha256).hexdigest()
    assert verify_stripe_signature(payload, f"t={ts},v1={sig}") is True


def test_verify_stripe_signature_invalid(settings):
    """Wrong v1 signature is rejected."""
    settings.STRIPE_WEBHOOK_SECRET = "whsec_real"
    ts = str(int(time.time()))
    assert verify_stripe_signature(b"stripe body", f"t={ts},v1=badsig") is False
