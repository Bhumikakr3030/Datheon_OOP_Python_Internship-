"""Observer interfaces and example order event listeners."""
from abc import ABC, abstractmethod
from threading import Lock

from .models import OrderEvent


class OrderObserver(ABC):
    @abstractmethod
    def on_order_event(self, event: OrderEvent) -> None:
        raise NotImplementedError


class _RecordingListener(OrderObserver):
    def __init__(self):
        self.__events = []
        self.__lock = Lock()

    def on_order_event(self, event):
        with self.__lock:
            self.__events.append(event)

    @property
    def events(self):
        with self.__lock:
            return tuple(self.__events)


class LogisticsListener(_RecordingListener):
    """Demo listener: records events for logistics workflow."""


class InvoicingListener(_RecordingListener):
    """Demo listener: records events for invoice workflow."""


class EmailListener(_RecordingListener):
    """Demo listener: records events for customer email workflow."""
