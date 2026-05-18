"""Use case: list all promo codes."""

from __future__ import annotations

from apps.payments.domain.entities import PromoCodeEntity
from apps.payments.domain.repositories import IPromoCodeRepository


class ListPromoCodesUseCase:
    """Return all promo codes."""

    def __init__(self, repo: IPromoCodeRepository) -> None:
        self._repo = repo

    def execute(self) -> list[PromoCodeEntity]:
        """Return all promo codes."""
        return self._repo.list_all()
