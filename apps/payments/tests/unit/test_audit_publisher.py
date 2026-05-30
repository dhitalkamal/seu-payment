"""Unit tests for the cross-service audit publisher."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch


def test_publish_audit_sends_to_audit_log_routing_key() -> None:
    """publish_audit sends a message with routing_key audit.log."""
    with patch("apps.payments.infrastructure.audit_publisher.pika") as mock_pika:
        mock_conn = MagicMock()
        mock_channel = MagicMock()
        mock_pika.BlockingConnection.return_value = mock_conn
        mock_conn.channel.return_value = mock_channel

        from apps.payments.infrastructure.audit_publisher import publish_audit

        request = MagicMock()
        request.META = {
            "HTTP_X_FORWARDED_FOR": "1.2.3.4",
            "HTTP_USER_AGENT": "TestAgent/1.0",
        }

        publish_audit(
            request=request,
            user_id=uuid.uuid4(),
            event_type="order.created",
        )

        mock_channel.basic_publish.assert_called_once()
        kwargs = mock_channel.basic_publish.call_args.kwargs
        assert kwargs["routing_key"] == "audit.log"


def test_publish_audit_swallows_connection_errors() -> None:
    """publish_audit does not raise when RabbitMQ is unavailable."""
    with patch("apps.payments.infrastructure.audit_publisher.pika") as mock_pika:
        mock_pika.BlockingConnection.side_effect = ConnectionError("no rabbit")

        from apps.payments.infrastructure.audit_publisher import publish_audit

        request = MagicMock()
        request.META = {}

        publish_audit(
            request=request,
            user_id=uuid.uuid4(),
            event_type="order.created",
        )
