"""Payment gateway implementations — Khalti, eSewa, Stripe, PayPal."""

from __future__ import annotations

from apps.payments.domain.gateway import IPaymentGateway
from apps.payments.infrastructure.gateways.esewa import EsewaGateway
from apps.payments.infrastructure.gateways.khalti import KhaltiGateway
from apps.payments.infrastructure.gateways.paypal import PayPalGateway
from apps.payments.infrastructure.gateways.stripe import StripeGateway

_REGISTRY: dict[str, type[IPaymentGateway]] = {
    "khalti": KhaltiGateway,
    "esewa": EsewaGateway,
    "stripe": StripeGateway,
    "paypal": PayPalGateway,
}


def get_gateway(name: str) -> IPaymentGateway:
    """Factory — return the gateway client for the given provider name.

    @param name - one of khalti, esewa, stripe, paypal
    @raises ValueError if the gateway name is unknown
    """
    cls = _REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"Unknown payment gateway: {name}")
    return cls()
