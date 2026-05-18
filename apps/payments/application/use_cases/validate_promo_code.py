"""Use case: validate a promo code and return its discount details."""

from __future__ import annotations

from datetime import datetime, timezone

from apps.payments.domain.entities import PromoCodeEntity
from apps.payments.domain.exceptions import InvalidPromoCodeError
from apps.payments.domain.repositories import IPromoCodeRepository


class ValidatePromoCodeUseCase:
    """Validate a promo code and return its entity if eligible."""

    def __init__(self, repo: IPromoCodeRepository) -> None:
        self._repo = repo

    def execute(self, *, code: str) -> PromoCodeEntity:
        """
        Fetch the promo code and assert it is active, unexpired, and under usage limit.

        Raises InvalidPromoCodeError for any failing condition so callers see one error type.
        """
        promo = self._repo.get_by_code(code)

        if not promo.is_active:
            raise InvalidPromoCodeError("Promo code is not active.")

        now = datetime.now(timezone.utc)
        if now > promo.valid_until:
            raise InvalidPromoCodeError("Promo code has expired.")

        # ! max_usage_count of 0 means unlimited
        if promo.max_usage_count > 0 and promo.used_count >= promo.max_usage_count:
            raise InvalidPromoCodeError("Promo code usage limit has been reached.")

        return promo
