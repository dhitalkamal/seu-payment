"""Use case: create a payment order, call the gateway, and return a payment URL."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from apps.payments.domain.entities import PaymentOrderEntity, PromoCodeEntity
from apps.payments.domain.exceptions import InvalidPromoCodeError, OrderAlreadyExistsError
from apps.payments.domain.gateway import IPaymentGateway, PaymentSession
from apps.payments.domain.repositories import IPaymentOrderRepository, IPromoCodeRepository

# ! platform fee varies by org plan — free=5%, starter=3%, pro=1%, ngo/enterprise=0%
PLAN_FEE_RATES: dict[str, Decimal] = {
    "free": Decimal("0.05"),
    "starter": Decimal("0.03"),
    "pro": Decimal("0.01"),
    "ngo": Decimal("0.00"),
    "enterprise": Decimal("0.00"),
}
# fallback for unknown plans
PLATFORM_FEE_RATE = Decimal("0.05")


class CreatePaymentOrderUseCase:
    """Create a payment order, call the gateway to initiate payment, return the payment URL."""

    def __init__(
        self,
        order_repo: IPaymentOrderRepository,
        promo_repo: IPromoCodeRepository,
        gateway_client: IPaymentGateway | None = None,
    ) -> None:
        self._orders = order_repo
        self._promos = promo_repo
        self._gateway = gateway_client

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
        customer_email: str = "",
        return_url: str = "",
        cancel_url: str = "",
        description: str = "Sansaar event registration",
        org_plan: str = "free",
    ) -> tuple[PaymentOrderEntity, PaymentSession | None]:
        """
        Calculate fees, apply promo, persist order, call gateway, store gateway_order_id.

        @param user_id - UUID from JWT
        @param event_id - the event being paid for
        @param registration_id - must be unique per order
        @param subtotal - base ticket price in NPR
        @param gateway - khalti | esewa | stripe | paypal
        @param idempotency_key - re-submitting the same key returns the existing order
        @param promo_code - optional case-insensitive promo code
        @param customer_email - buyer email from JWT (passed to gateway)
        @param return_url - where the gateway redirects on success
        @param cancel_url - where the gateway redirects on failure/cancel
        @param description - label shown on the gateway payment page
        @param org_plan - the organiser's plan (determines platform fee rate)
        @returns tuple of (order, payment_session) — session is None for idempotent re-fetches
        @raises OrderAlreadyExistsError if another order exists for this registration
        @raises InvalidPromoCodeError if the promo is invalid
        @raises PaymentGatewayError if the gateway rejects or is unreachable
        """
        existing = self._orders.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            return existing, None

        if self._orders.has_order_for_registration(registration_id):
            raise OrderAlreadyExistsError("An order already exists for this registration.")

        discount_amount = Decimal("0.00")
        promo_id: uuid.UUID | None = None

        if promo_code:
            promo = self._promos.get_by_code(promo_code)
            self._validate_promo(promo)
            discount_amount = self._apply_promo(promo, subtotal)
            promo_id = promo.id

        # ! look up fee rate by org plan — fallback to 5% for unknown plans
        fee_rate = PLAN_FEE_RATES.get(org_plan, PLATFORM_FEE_RATE)
        platform_fee = (subtotal * fee_rate).quantize(Decimal("0.01"))
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

        # * call the gateway to initiate the payment session
        session: PaymentSession | None = None
        if self._gateway is not None:
            session = self._gateway.initiate(
                order_id=str(result.id),
                amount=total_amount,
                currency=result.currency,
                description=description,
                customer_email=customer_email,
                return_url=return_url,
                cancel_url=cancel_url,
            )
            # ! persist the gateway_order_id so webhooks can match this order
            result.gateway_order_id = session.gateway_order_id
            result.status = "processing"
            result = self._orders.update(result)

        return result, session

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
