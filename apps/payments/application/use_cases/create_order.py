"""Use case: create a payment order with fee calculation and optional promo code."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from apps.payments.domain.entities import PaymentOrderEntity, PromoCodeEntity
from apps.payments.domain.exceptions import InvalidPromoCodeError, OrderAlreadyExistsError
from apps.payments.domain.repositories import IPaymentOrderRepository, IPromoCodeRepository

# ! platform fee is 5% of subtotal on the free plan
PLATFORM_FEE_RATE = Decimal("0.05")


class CreatePaymentOrderUseCase:
    """Create a payment order, applying fee formula and optional promo discount."""

    def __init__(
        self,
        order_repo: IPaymentOrderRepository,
        promo_repo: IPromoCodeRepository,
    ) -> None:
        self._orders = order_repo
        self._promos = promo_repo

    def execute(
        self,
        *,
        user_id: uuid.UUID,
        event_id: uuid.UUID,
        registration_id: uuid.UUID,
        subtotal: Decimal,
        gateway: str,
        idempotency_key: uuid.UUID,
        promo_code: str | None = None,
    ) -> PaymentOrderEntity:
        """
        Calculate fees, apply promo if given, and persist the order.

        @param user_id - UUID from JWT
        @param event_id - the event being paid for
        @param registration_id - must be unique per order
        @param subtotal - base ticket price in NPR
        @param gateway - khalti | esewa | stripe | paypal
        @param idempotency_key - re-submitting the same key returns the existing order
        @param promo_code - optional case-insensitive promo code
        @returns the created or previously created PaymentOrderEntity
        @raises OrderAlreadyExistsError if another order exists for this registration
        @raises InvalidPromoCodeError if the promo is missing, expired, inactive, or exhausted
        """
        existing = self._orders.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            return existing

        if self._orders.has_order_for_registration(registration_id):
            raise OrderAlreadyExistsError("An order already exists for this registration.")

        discount_amount = Decimal("0.00")
        promo_id: uuid.UUID | None = None

        if promo_code:
            promo = self._promos.get_by_code(promo_code)
            self._validate_promo(promo)
            discount_amount = self._apply_promo(promo, subtotal)
            promo_id = promo.id

        platform_fee = (subtotal * PLATFORM_FEE_RATE).quantize(Decimal("0.01"))
        total_amount = subtotal - discount_amount + platform_fee

        now = datetime.now(timezone.utc)
        order = PaymentOrderEntity(
            id=uuid.uuid4(),
            user_id=user_id,
            event_id=event_id,
            registration_id=registration_id,
            subtotal=subtotal,
            discount_amount=discount_amount,
            tax_amount=Decimal("0.00"),
            gateway_fee=Decimal("0.00"),
            platform_fee=platform_fee,
            total_amount=total_amount,
            currency="NPR",
            status="created",
            gateway=gateway,
            gateway_order_id="",
            idempotency_key=idempotency_key,
            created_at=now,
            updated_at=now,
        )
        result = self._orders.create(order)

        if promo_id is not None:
            self._promos.increment_usage(promo_id)

        return result

    def _validate_promo(self, promo: PromoCodeEntity) -> None:
        """Raise InvalidPromoCodeError if the promo cannot be applied."""
        now = datetime.now(timezone.utc)
        if not promo.is_active:
            raise InvalidPromoCodeError("Promo code is not active.")
        if now < promo.valid_from or now > promo.valid_until:
            raise InvalidPromoCodeError("Promo code is expired or not yet valid.")
        if promo.used_count >= promo.max_usage_count:
            raise InvalidPromoCodeError("Promo code has reached its usage limit.")

    def _apply_promo(self, promo: PromoCodeEntity, subtotal: Decimal) -> Decimal:
        """Return the discount amount based on the promo type."""
        if promo.discount_type == "percentage":
            return (subtotal * promo.discount_value / Decimal("100")).quantize(Decimal("0.01"))
        return min(promo.discount_value, subtotal)
