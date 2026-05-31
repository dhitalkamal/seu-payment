"""Stripe Connect gateway: account creation, onboarding links, and transfers."""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal

import stripe
from django.conf import settings

from apps.payments.domain.exceptions import PayoutError

logger = logging.getLogger(__name__)


class StripeConnectGateway:
    """Wraps the Stripe Connect API for account creation and fund transfers."""

    def _client(self) -> stripe.StripeClient:
        """Return a configured Stripe client. Raises PayoutError if key missing."""
        key = settings.STRIPE_SECRET_KEY
        if not key:
            raise PayoutError("STRIPE_SECRET_KEY is not configured.")
        return stripe.StripeClient(key)

    def create_account(self, org_id: uuid.UUID) -> str:
        """Create a Stripe Express connected account and return its account ID."""
        client = self._client()
        try:
            account = client.accounts.create(
                params={
                    "type": "express",
                    "metadata": {"org_id": str(org_id)},
                }
            )
            return account.id
        except stripe.StripeError as exc:
            logger.error("Stripe create_account failed: %s", exc)
            raise PayoutError(f"Stripe create_account failed: {exc}") from exc

    def create_account_link(self, stripe_account_id: str, return_url: str, refresh_url: str) -> str:
        """Generate a Stripe Connect onboarding URL for the given account."""
        client = self._client()
        try:
            link = client.account_links.create(
                params={
                    "account": stripe_account_id,
                    "refresh_url": refresh_url,
                    "return_url": return_url,
                    "type": "account_onboarding",
                }
            )
            return link.url
        except stripe.StripeError as exc:
            logger.error("Stripe create_account_link failed: %s", exc)
            raise PayoutError(f"Stripe create_account_link failed: {exc}") from exc

    def transfer(
        self,
        *,
        stripe_account_id: str,
        amount: Decimal,
        currency: str,
        description: str,
    ) -> str:
        """Transfer funds to a connected account and return the transfer ID."""
        client = self._client()
        stripe_currency = currency.lower()
        amount_minor = int(amount * 100) if stripe_currency in ("usd", "eur", "gbp") else int(amount)
        try:
            transfer = client.transfers.create(
                params={
                    "amount": amount_minor,
                    "currency": stripe_currency,
                    "destination": stripe_account_id,
                    "description": description,
                }
            )
            return transfer.id
        except stripe.StripeError as exc:
            logger.error("Stripe transfer failed: %s", exc)
            raise PayoutError(f"Stripe transfer failed: {exc}") from exc
