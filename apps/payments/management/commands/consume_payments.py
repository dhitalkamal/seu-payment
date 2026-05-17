"""Django management command to start the payment RabbitMQ consumer."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.payments.infrastructure.consumer import start_consumer


class Command(BaseCommand):
    """Starts the RabbitMQ consumer for payment-related events."""

    help = "Start the payment service RabbitMQ consumer."

    def handle(self, *args: object, **options: object) -> None:
        """Run the consumer. Blocks indefinitely."""
        self.stdout.write("Starting payment consumer...")
        start_consumer()
