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
