"""Abstract payment gateway interface; all four providers implement this."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PaymentSession:
    """Value object returned by a gateway after initiating a payment.

    gateway_order_id - the provider's own ID for this payment (pidx, session_id, etc.)
    payment_url - where the client should be redirected to complete the payment
    raw_response - the full provider response for debugging and audit
    """

    gateway_order_id: str
    payment_url: str
    raw_response: dict


class IPaymentGateway(ABC):
    """Contract every payment gateway must fulfil."""

    @abstractmethod
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
        Start a payment session with the provider.

        @param order_id - our internal order UUID as a string (used as purchase_order_id)
        @param amount - total to charge the customer
        @param currency - ISO currency code (NPR, USD, etc.)
        @param description - short label for the payment
        @param customer_email - buyer's email
        @param return_url - URL the provider redirects to after success
        @param cancel_url - URL the provider redirects to after cancellation/failure
        @returns PaymentSession with gateway_order_id and payment_url
        @raises PaymentGatewayError on network or API failures
        """
        ...

    @abstractmethod
    def refund(self, *, gateway_order_id: str, amount: Decimal) -> str:
        """
        Issue a refund for a previously completed payment.

        @param gateway_order_id - the provider's own ID for the original payment
        @param amount - amount to refund in the original currency
        @returns the provider's refund ID for audit purposes
        @raises PaymentGatewayError on network or API failures
        """
        ...
