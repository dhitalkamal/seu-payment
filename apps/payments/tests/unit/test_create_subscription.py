"""Tests for create subscription use case - free downgrade and gateway-first flow."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from apps.payments.application.use_cases.create_subscription import CreateSubscriptionUseCase
from apps.payments.tests.unit.fakes import FakeSubscriptionRepository


class TestDowngradeToFree:
    """Switching to free plan cancels existing and returns free sub."""

    def test_downgrade_cancels_existing(self) -> None:
        repo = FakeSubscriptionRepository()
        org_id = uuid.uuid4()
        existing = MagicMock(id=uuid.uuid4(), plan="starter", status="active")
        repo._active = {org_id: existing}

        uc = CreateSubscriptionUseCase(sub_repo=repo)
        sub, session = uc.execute(org_id=org_id, plan="free", gateway="none")

        assert sub.plan == "free"
        assert session is None
        assert existing.status == "cancelled"

    def test_free_plan_no_gateway_call(self) -> None:
        repo = FakeSubscriptionRepository()
        mock_gw = MagicMock()

        uc = CreateSubscriptionUseCase(sub_repo=repo, gateway_client=mock_gw)
        sub, session = uc.execute(org_id=uuid.uuid4(), plan="free", gateway="none")

        assert sub.plan == "free"
        mock_gw.initiate.assert_not_called()


class TestPaidPlanGatewayFirst:
    """Paid plans call gateway before saving subscription."""

    def test_gateway_failure_does_not_save_subscription(self) -> None:
        repo = FakeSubscriptionRepository()
        mock_gw = MagicMock()
        mock_gw.initiate.side_effect = Exception("gateway down")

        uc = CreateSubscriptionUseCase(sub_repo=repo, gateway_client=mock_gw)
        try:
            uc.execute(org_id=uuid.uuid4(), plan="starter", gateway="khalti")
        except Exception:
            pass

        assert len(repo._subs) == 0

    def test_gateway_success_saves_pending_subscription(self) -> None:
        repo = FakeSubscriptionRepository()
        mock_gw = MagicMock()
        mock_gw.initiate.return_value = MagicMock(gateway_order_id="gw-123")

        uc = CreateSubscriptionUseCase(sub_repo=repo, gateway_client=mock_gw)
        sub, session = uc.execute(org_id=uuid.uuid4(), plan="starter", gateway="khalti")

        assert sub.status == "pending"
        assert sub.gateway_subscription_id == "gw-123"
        assert len(repo._subs) == 1
