from abc import ABC, abstractmethod
from typing import Protocol

from .models import Notification, DeliveryResult


class NotificationChannel(ABC):
    """Interface implemented by every delivery channel."""

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def send(self, notification: Notification) -> DeliveryResult:
        raise NotImplementedError


class NotificationFormatter(Protocol):
    """Protocol for formatting content without coupling it to a channel."""

    def format(self, notification: Notification, channel_name: str) -> str:
        ...


class NotificationLogger(Protocol):
    """Protocol for delivery audit/logging implementations."""

    def record(self, result: DeliveryResult) -> None:
        ...
