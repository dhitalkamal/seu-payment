"""Pure Python domain entities for the payments module with no framework dependencies."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(slots=True)
class PaymentOrderEntity:
    """A payment order for a single event registration."""

    id: uuid.UUID
    user_id: uuid.UUID
    event_id: uuid.UUID
    registration_id: uuid.UUID
    subtotal: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    gateway_fee: Decimal
    platform_fee: Decimal
    total_amount: Decimal
    currency: str
    status: str
    gateway: str
    gateway_order_id: str
    idempotency_key: uuid.UUID
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    # * stored on creation so notification-service can email the buyer on completion
    customer_email: str = ""
    customer_first_name: str = ""


@dataclass(slots=True)
class RefundEntity:
    """A refund request against a completed payment order."""

    id: uuid.UUID
    order_id: uuid.UUID
    amount: Decimal
    reason: str
    status: str
    gateway_refund_id: str
    created_at: datetime


@dataclass(slots=True)
class DisputeEntity:
    """A payment dispute raised by a user against a completed order."""

    id: uuid.UUID
    order_id: uuid.UUID
    user_id: uuid.UUID
    status: str
    reason: str
    description: str
    evidence: dict
    gateway_dispute_id: str
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class PromoCodeEntity:
    """A discount code applied at order creation time."""

    id: uuid.UUID
    code: str
    discount_type: str
    discount_value: Decimal
    valid_from: datetime
    valid_until: datetime
    is_active: bool
    max_usage_count: int
    used_count: int
    created_at: datetime


# * ---- Subscription billing ----


@dataclass(slots=True)
class SubscriptionEntity:
    """An organization's subscription to a platform plan."""

    id: uuid.UUID
    org_id: uuid.UUID
    plan: str
    status: str  # active | cancelled | past_due | expired
    gateway: str
    gateway_subscription_id: str
    amount: Decimal
    currency: str
    current_period_start: datetime
    current_period_end: datetime
    created_at: datetime
    updated_at: datetime
    cancelled_at: datetime | None = None


@dataclass(slots=True)
class SubscriptionPaymentEntity:
    """A single payment record in a subscription's billing history."""

    id: uuid.UUID
    subscription_id: uuid.UUID
    amount: Decimal
    currency: str
    status: str  # completed | failed
    gateway_transaction_id: str
    period_start: datetime
    period_end: datetime
    paid_at: datetime
