from threading import Lock
from typing import List

from .models import DeliveryResult


class InMemoryNotificationLogger:
    """Small logger adapter suitable for demos and tests."""

    def __init__(self):
        self.__results: List[DeliveryResult] = []
        self.__lock = Lock()

    def record(self, result: DeliveryResult) -> None:
        with self.__lock:
            self.__results.append(result)

    @property
    def results(self) -> tuple[DeliveryResult, ...]:
        with self.__lock:
            return tuple(self.__results)
