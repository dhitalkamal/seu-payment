"""Use case: create a new promo code."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from apps.payments.domain.entities import PromoCodeEntity
from apps.payments.domain.repositories import IPromoCodeRepository


class CreatePromoCodeUseCase:
    """Create and persist a new promo code."""

    def __init__(self, repo: IPromoCodeRepository) -> None:
        self._repo = repo

    def execute(
        self,
        *,
        code: str,
        discount_type: str,
        discount_value: Decimal,
        valid_from: datetime,
        valid_until: datetime,
        max_usage_count: int = 0,
    ) -> PromoCodeEntity:
        """Persist a new promo code and return it."""
        entity = PromoCodeEntity(
            id=uuid.uuid4(),
            code=code.upper(),
            discount_type=discount_type,
            discount_value=discount_value,
            valid_from=valid_from,
            valid_until=valid_until,
            is_active=True,
            max_usage_count=max_usage_count,
            used_count=0,
            created_at=datetime.now(timezone.utc),
        )
        return self._repo.create(entity)
