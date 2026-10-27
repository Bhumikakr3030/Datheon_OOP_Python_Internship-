"""Demo channel adapters.

These adapters simulate delivery. Connect provider SDKs/API clients in these
classes for real delivery; keep provider-specific code out of NotificationService.
"""
from .interfaces import NotificationChannel, NotificationFormatter
from .models import Notification, DeliveryResult


class _SimulatedChannel(NotificationChannel):
    def __init__(self, formatter: NotificationFormatter):
        self._formatter = formatter

    def _send_simulated(self, notification: Notification) -> DeliveryResult:
        formatted = self._formatter.format(notification, self.name)
        # Deliberately no real network call. A provider adapter can replace this.
        if not formatted.strip():
            return DeliveryResult.create(
                self.name, notification.recipient, notification.notification_id,
                False, "Formatted message was empty."
            )
        return DeliveryResult.create(
            self.name, notification.recipient, notification.notification_id,
            True, f"Simulated delivery via {self.name}; no provider API called."
        )


class EmailChannel(_SimulatedChannel):
    @property
    def name(self) -> str:
        return "email"

    def send(self, notification: Notification) -> DeliveryResult:
        return self._send_simulated(notification)


class SMSChannel(_SimulatedChannel):
    @property
    def name(self) -> str:
        return "sms"

    def send(self, notification: Notification) -> DeliveryResult:
        return self._send_simulated(notification)


class SlackChannel(_SimulatedChannel):
    @property
    def name(self) -> str:
        return "slack"

    def send(self, notification: Notification) -> DeliveryResult:
        return self._send_simulated(notification)


class WhatsAppChannel(_SimulatedChannel):
    @property
    def name(self) -> str:
        return "whatsapp"

    def send(self, notification: Notification) -> DeliveryResult:
        return self._send_simulated(notification)
