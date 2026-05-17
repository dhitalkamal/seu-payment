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
    """Log registration_created events — no action needed, order is created via API."""
    logger.info(
        "Received participation.registration.created for event_id=%s user_id=%s",
        payload.get("event_id"),
        payload.get("user_id"),
    )


_HANDLERS: dict = {
    "participation.registration.created": _handle_registration_created,
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
            logger.debug("No handler for event %s — acking.", event_name)
    except Exception:
        logger.exception("Error processing event %s.", event_name)
    finally:
        channel.basic_ack(delivery_tag=method.delivery_tag)


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
