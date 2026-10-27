"""Extensible SOLID notification dispatch library."""
from .models import Notification, DeliveryResult
from .interfaces import NotificationChannel, NotificationFormatter, NotificationLogger
from .service import NotificationService
from .formatters import PlainTextFormatter
from .logging_adapters import InMemoryNotificationLogger
from .channels import EmailChannel, SMSChannel, SlackChannel, WhatsAppChannel

__all__ = [
    "Notification", "DeliveryResult", "NotificationChannel",
    "NotificationFormatter", "NotificationLogger", "NotificationService",
    "PlainTextFormatter", "InMemoryNotificationLogger", "EmailChannel",
    "SMSChannel", "SlackChannel", "WhatsAppChannel",
]
