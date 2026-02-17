"""Unit tests for AdminOrderListView and list_all on the order repository."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from apps.payments.tests.unit.fakes import FakePaymentOrderRepository, make_order

# * ---- repository-level tests ----


def test_list_all_orders_returns_all_orders() -> None:
    """FakePaymentOrderRepository.list_all returns every stored order."""
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()
    orders = [make_order(user_id=user_a), make_order(user_id=user_b)]
    repo = FakePaymentOrderRepository(orders)
    result = repo.list_all()
    assert len(result) == 2
    assert {o.id for o in result} == {orders[0].id, orders[1].id}


def test_list_all_orders_not_scoped_to_user() -> None:
    """list_all returns orders for multiple different users in a single call."""
    ids = [uuid.uuid4() for _ in range(4)]
    orders = [make_order(user_id=uid) for uid in ids]
    repo = FakePaymentOrderRepository(orders)
    result = repo.list_all()
    returned_user_ids = {o.user_id for o in result}
    assert returned_user_ids == set(ids)


def test_list_all_orders_empty() -> None:
    """list_all returns an empty list when the store is empty."""
    repo = FakePaymentOrderRepository()
    assert repo.list_all() == []


# * ---- view permission tests ----


def test_admin_order_list_view_requires_staff() -> None:
    """IsSuperAdminFromAllowedIP denies non-staff users."""
    from apps.common.permissions import IsSuperAdminFromAllowedIP

    perm = IsSuperAdminFromAllowedIP()
    request = MagicMock()
    request.user.is_authenticated = True
    request.user.is_staff = False
    assert perm.has_permission(request, MagicMock()) is False


def test_admin_order_list_view_requires_authenticated() -> None:
    """IsSuperAdminFromAllowedIP denies unauthenticated requests."""
    from apps.common.permissions import IsSuperAdminFromAllowedIP

    perm = IsSuperAdminFromAllowedIP()
    request = MagicMock()
    request.user.is_authenticated = False
    assert perm.has_permission(request, MagicMock()) is False


def test_admin_order_list_view_allows_staff_with_no_ip_restriction() -> None:
    """IsSuperAdminFromAllowedIP allows staff when SUPERADMIN_ALLOWED_IPS is empty."""
    from unittest.mock import patch

    from apps.common.permissions import IsSuperAdminFromAllowedIP

    perm = IsSuperAdminFromAllowedIP()
    request = MagicMock()
    request.user.is_authenticated = True
    request.user.is_staff = True

    with patch("apps.common.permissions.settings") as mock_settings:
        mock_settings.SUPERADMIN_ALLOWED_IPS = []
        assert perm.has_permission(request, MagicMock()) is True
