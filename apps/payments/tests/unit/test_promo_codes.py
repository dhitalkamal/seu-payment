"""Unit tests for promo code use cases."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from apps.payments.domain.exceptions import InvalidPromoCodeError
from apps.payments.tests.unit.fakes import FakePromoCodeRepository


def _make_promo_repo(
    code: str = "SAVE10",
    discount_type: str = "percentage",
    discount_value: Decimal = Decimal("10.00"),
    is_active: bool = True,
    max_usage_count: int = 100,
    used_count: int = 0,
    days_valid: int = 30,
):
    """Build a FakePromoCodeRepository with one valid promo code."""
    from apps.payments.domain.entities import PromoCodeEntity

    now = datetime.now(timezone.utc)
    promo = PromoCodeEntity(
        id=uuid.uuid4(),
        code=code,
        discount_type=discount_type,
        discount_value=discount_value,
        valid_from=now - timedelta(days=1),
        valid_until=now + timedelta(days=days_valid),
        is_active=is_active,
        max_usage_count=max_usage_count,
        used_count=used_count,
        created_at=now,
    )
    return FakePromoCodeRepository([promo])


def test_validate_promo_returns_discount_info():
    """ValidatePromoCodeUseCase returns the promo entity for a valid code."""
    from apps.payments.application.use_cases.validate_promo_code import ValidatePromoCodeUseCase

    repo = _make_promo_repo(code="SAVE10", discount_type="percentage", discount_value=Decimal("10"))
    result = ValidatePromoCodeUseCase(repo).execute(code="SAVE10")
    assert result.code == "SAVE10"
    assert result.discount_type == "percentage"


def test_validate_promo_case_insensitive():
    """Promo code lookup is case-insensitive."""
    from apps.payments.application.use_cases.validate_promo_code import ValidatePromoCodeUseCase

    repo = _make_promo_repo(code="SAVE10")
    result = ValidatePromoCodeUseCase(repo).execute(code="save10")
    assert result.code == "SAVE10"


def test_validate_promo_inactive_raises():
    """Raises InvalidPromoCodeError when promo is not active."""
    from apps.payments.application.use_cases.validate_promo_code import ValidatePromoCodeUseCase

    repo = _make_promo_repo(is_active=False)
    with pytest.raises(InvalidPromoCodeError):
        ValidatePromoCodeUseCase(repo).execute(code="SAVE10")


def test_validate_promo_exhausted_raises():
    """Raises InvalidPromoCodeError when usage limit is reached."""
    from apps.payments.application.use_cases.validate_promo_code import ValidatePromoCodeUseCase

    repo = _make_promo_repo(max_usage_count=5, used_count=5)
    with pytest.raises(InvalidPromoCodeError):
        ValidatePromoCodeUseCase(repo).execute(code="SAVE10")


def test_validate_promo_expired_raises():
    """Raises InvalidPromoCodeError when promo has expired."""
    from apps.payments.application.use_cases.validate_promo_code import ValidatePromoCodeUseCase

    repo = _make_promo_repo(days_valid=-1)
    with pytest.raises(InvalidPromoCodeError):
        ValidatePromoCodeUseCase(repo).execute(code="SAVE10")


def test_create_promo_code_success():
    """CreatePromoCodeUseCase creates and persists a promo code."""
    from apps.payments.application.use_cases.create_promo_code import CreatePromoCodeUseCase

    now = datetime.now(timezone.utc)
    repo = FakePromoCodeRepository()
    result = CreatePromoCodeUseCase(repo).execute(
        code="EARLYBIRD",
        discount_type="percentage",
        discount_value=Decimal("20"),
        valid_from=now,
        valid_until=now + timedelta(days=30),
        max_usage_count=50,
    )
    assert result.code == "EARLYBIRD"
    assert len(repo.list_all()) == 1


def test_list_promo_codes_returns_all():
    """ListPromoCodesUseCase returns all stored promo codes."""
    from apps.payments.application.use_cases.list_promo_codes import ListPromoCodesUseCase

    repo = _make_promo_repo()
    results = ListPromoCodesUseCase(repo).execute()
    assert len(results) == 1
