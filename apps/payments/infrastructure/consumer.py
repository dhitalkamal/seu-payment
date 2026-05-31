"""RabbitMQ consumer for incoming participation events relevant to payments."""

from __future__ import annotations

import json
import logging

import pika
from django.conf import settings

logger = logging.getLogger(__name__)

_EXCHANGE = "sansaar"
_EXCHANGE_TYPE = "topic"
_QUEUE = "payment.events"
_ROUTING_KEY = "participation.#"


def _handle_registration_created(payload: dict) -> None:
    """Log registration_created events - no action needed, order is created via API."""
    logger.info(
        "Received participation.registration.created for event_id=%s user_id=%s",
        payload.get("event_id"),
        payload.get("user_id"),
    )


def _handle_registration_cancelled(payload: dict) -> None:
    """Flag the related order for manual refund review when a registration is cancelled."""
    from apps.payments.infrastructure.models import PaymentOrder

    order_id_str = payload.get("order_id")
    user_id_str = payload.get("user_id")
    event_id_str = payload.get("event_id")

    if order_id_str:
        try:
            order = PaymentOrder.objects.get(pk=order_id_str)
            if order.status == "completed":
                order.status = "refund_pending"
                order.save(update_fields=["status", "updated_at"])
                logger.info("Order %s flagged for manual refund review.", order_id_str)
            return
        except PaymentOrder.DoesNotExist:
            logger.warning("Order %s not found for refund flagging.", order_id_str)
        except Exception:
            logger.exception("Failed to flag order %s for refund.", order_id_str)
        return

    # fallback: find by user_id + event_id if no order_id provided
    if user_id_str and event_id_str:
        try:
            found = (
                PaymentOrder.objects.filter(
                    user_id=user_id_str,
                    event_id=event_id_str,
                    status="completed",
                )
                .order_by("-created_at")
                .first()
            )
            if found:
                found.status = "refund_pending"
                found.save(update_fields=["status", "updated_at"])
                logger.info("Order %s flagged for manual refund review (lookup by user+event).", found.pk)
            else:
                logger.info("No completed order found for user %s event %s, skipping refund.", user_id_str, event_id_str)
        except Exception:
            logger.exception("Failed to flag order for refund. user=%s event=%s", user_id_str, event_id_str)
    else:
        logger.warning("participation.registration.cancelled missing order_id and user_id/event_id: %s", payload)


_HANDLERS: dict = {
    "participation.registration.created": _handle_registration_created,
    "participation.registration.cancelled": _handle_registration_cancelled,
}


def _handle_message(
    channel: pika.channel.Channel,
    method: pika.spec.Basic.Deliver,
    properties: pika.spec.BasicProperties,
    body: bytes,
) -> None:
    """Dispatch incoming message to the appropriate handler."""
    event_name = method.routing_key
    try:
        payload = json.loads(body)
        handler = _HANDLERS.get(event_name)
        if handler:
            handler(payload)
        else:
            logger.debug("No handler for event %s, acking.", event_name)
        channel.basic_ack(delivery_tag=method.delivery_tag)
    except Exception:
        logger.exception("Error processing event %s, sending to dead-letter.", event_name)
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def start_consumer() -> None:
    """Connect to RabbitMQ and begin consuming payment-relevant events."""
    params = pika.URLParameters(settings.RABBITMQ_URL)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()

    channel.exchange_declare(exchange=_EXCHANGE, exchange_type=_EXCHANGE_TYPE, durable=True)
    channel.queue_declare(queue=_QUEUE, durable=True)
    channel.queue_bind(queue=_QUEUE, exchange=_EXCHANGE, routing_key=_ROUTING_KEY)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=_QUEUE, on_message_callback=_handle_message)

    logger.info("Payment consumer started. Waiting for messages on %s.", _ROUTING_KEY)
    channel.start_consuming()
