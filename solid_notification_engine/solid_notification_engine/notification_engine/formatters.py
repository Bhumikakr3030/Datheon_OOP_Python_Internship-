from .models import Notification


class PlainTextFormatter:
    """Simple formatter; replace with HTML, Markdown, or localized formatters."""

    def format(self, notification: Notification, channel_name: str) -> str:
        return f"{notification.subject}\n\n{notification.message}"
