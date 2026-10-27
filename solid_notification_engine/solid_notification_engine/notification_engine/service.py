from typing import Dict, Iterable

from .interfaces import NotificationChannel, NotificationFormatter, NotificationLogger
from .models import Notification, DeliveryResult
from .formatters import PlainTextFormatter
from .logging_adapters import InMemoryNotificationLogger


class NotificationService:
    """Orchestrates notifications; all collaborators are injected.

    The service depends on abstractions, not concrete provider classes.
    Add a new channel by implementing NotificationChannel and injecting it.
    """

    def __init__(
        self,
        channels: Iterable[NotificationChannel],
        formatter: NotificationFormatter = None,
        logger: NotificationLogger = None,
    ):
        channel_map: Dict[str, NotificationChannel] = {}
        for channel in channels:
            if not isinstance(channel, NotificationChannel):
                raise TypeError("Every channel must implement NotificationChannel.")
            key = channel.name.strip().lower()
            if not key:
                raise ValueError("Channel name cannot be empty.")
            if key in channel_map:
                raise ValueError(f"Duplicate notification channel: {key}")
            channel_map[key] = channel

        self.__channels = channel_map
        self.__formatter = formatter or PlainTextFormatter()
        self.__logger = logger or InMemoryNotificationLogger()

    @property
    def available_channels(self) -> tuple[str, ...]:
        return tuple(sorted(self.__channels.keys()))

    def send(self, channel_name: str, notification: Notification) -> DeliveryResult:
        if not isinstance(channel_name, str) or not channel_name.strip():
            raise ValueError("Channel name cannot be empty.")
        if not isinstance(notification, Notification):
            raise TypeError("notification must be a Notification instance.")

        key = channel_name.strip().lower()
        try:
            channel = self.__channels[key]
        except KeyError:
            raise ValueError(
                f"Unsupported channel '{key}'. Available: {self.available_channels}"
            ) from None

        result = channel.send(notification)
        self.__logger.record(result)
        return result

    def send_to_many(self, channel_names, notification: Notification) -> tuple[DeliveryResult, ...]:
        """Send to each requested channel; return results in request order."""
        results = []
        for channel_name in channel_names:
            results.append(self.send(channel_name, notification))
        return tuple(results)
