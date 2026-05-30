"""Unit tests for payment plan client."""

from __future__ import annotations


class TestHttpPlanClient:
    """Verify the plan client falls back safely when management-service is unavailable."""

    def test_fallback_to_free_on_connection_error(self) -> None:
        from apps.payments.infrastructure.plan_client import HttpPlanClient
        import uuid

        client = HttpPlanClient("http://nonexistent-host:9999")
        result = client.get_org_plan(uuid.uuid4())
        assert result == "free"
