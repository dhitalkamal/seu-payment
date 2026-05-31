"""Unit tests for StripeConnectGateway — mocks the Stripe SDK."""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from apps.payments.domain.exceptions import PayoutError


def test_create_account_returns_account_id() -> None:
    """create_account calls Stripe and returns the new account ID."""
    from apps.payments.infrastructure.gateways.stripe_connect import StripeConnectGateway

    mock_client = MagicMock()
    mock_client.accounts.create.return_value = MagicMock(id="acct_test_123")

    gw = StripeConnectGateway()
    with patch.object(gw, "_client", return_value=mock_client):
        result = gw.create_account(uuid.uuid4())

    assert result == "acct_test_123"


def test_create_account_raises_payout_error_on_stripe_error() -> None:
    """create_account wraps StripeError in PayoutError."""
    import stripe

    from apps.payments.infrastructure.gateways.stripe_connect import StripeConnectGateway

    mock_client = MagicMock()
    mock_client.accounts.create.side_effect = stripe.StripeError("network failure")

    gw = StripeConnectGateway()
    with patch.object(gw, "_client", return_value=mock_client):
        with pytest.raises(PayoutError):
            gw.create_account(uuid.uuid4())


def test_create_account_link_returns_url() -> None:
    """create_account_link returns the onboarding URL from Stripe."""
    from apps.payments.infrastructure.gateways.stripe_connect import StripeConnectGateway

    mock_client = MagicMock()
    mock_client.account_links.create.return_value = MagicMock(url="https://connect.stripe.com/onboarding/acct_test_123")

    gw = StripeConnectGateway()
    with patch.object(gw, "_client", return_value=mock_client):
        result = gw.create_account_link("acct_test_123", "https://example.com/return", "https://example.com/refresh")

    assert result == "https://connect.stripe.com/onboarding/acct_test_123"


def test_transfer_returns_transfer_id() -> None:
    """transfer calls Stripe and returns the transfer ID."""
    from apps.payments.infrastructure.gateways.stripe_connect import StripeConnectGateway

    mock_client = MagicMock()
    mock_client.transfers.create.return_value = MagicMock(id="tr_test_abc")

    gw = StripeConnectGateway()
    with patch.object(gw, "_client", return_value=mock_client):
        result = gw.transfer(
            stripe_account_id="acct_test_123",
            amount=Decimal("500.00"),
            currency="USD",
            description="Payout",
        )

    assert result == "tr_test_abc"


def test_transfer_raises_payout_error_on_stripe_error() -> None:
    """transfer wraps StripeError in PayoutError."""
    import stripe

    from apps.payments.infrastructure.gateways.stripe_connect import StripeConnectGateway

    mock_client = MagicMock()
    mock_client.transfers.create.side_effect = stripe.StripeError("transfer failed")

    gw = StripeConnectGateway()
    with patch.object(gw, "_client", return_value=mock_client):
        with pytest.raises(PayoutError):
            gw.transfer(
                stripe_account_id="acct_test_123",
                amount=Decimal("500.00"),
                currency="USD",
                description="Payout",
            )
