"""Factory Method-style payment handler creation and polymorphic handlers."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from uuid import uuid4

from .models import Order


@dataclass(frozen=True)
class PaymentResult:
    payment_id: str
    provider: str
    success: bool
    amount: Decimal
    currency: str
    message: str


class PaymentHandler(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def pay(self, order: Order) -> PaymentResult:
        raise NotImplementedError


class CreditCardPayment(PaymentHandler):
    @property
    def provider_name(self):
        return "credit_card"

    def pay(self, order):
        return PaymentResult(str(uuid4()), self.provider_name, True,
                             order.amount, order.currency,
                             "Demo payment accepted; no card processor called.")


class UPIPayment(PaymentHandler):
    @property
    def provider_name(self):
        return "upi"

    def pay(self, order):
        return PaymentResult(str(uuid4()), self.provider_name, True,
                             order.amount, order.currency,
                             "Demo UPI payment accepted; no UPI provider called.")


class PayPalPayment(PaymentHandler):
    @property
    def provider_name(self):
        return "paypal"

    def pay(self, order):
        return PaymentResult(str(uuid4()), self.provider_name, True,
                             order.amount, order.currency,
                             "Demo PayPal payment accepted; no PayPal API called.")


class CryptoPayment(PaymentHandler):
    @property
    def provider_name(self):
        return "crypto"

    def pay(self, order):
        return PaymentResult(str(uuid4()), self.provider_name, True,
                             order.amount, order.currency,
                             "Demo crypto payment accepted; no blockchain transaction.")


class PaymentFactory:
    """Registry-based factory: extend via registration, not core dispatch edits."""

    def __init__(self):
        self.__builders = {}

    def register(self, name: str, builder):
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Payment method name cannot be empty.")
        if not callable(builder):
            raise TypeError("Payment builder must be callable.")
        key = name.strip().lower()
        if key in self.__builders:
            raise ValueError(f"Payment method already registered: {key}")
        self.__builders[key] = builder

    def create(self, name: str) -> PaymentHandler:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Payment method must be a non-empty string.")
        key = name.strip().lower()
        try:
            handler = self.__builders[key]()
        except KeyError:
            raise ValueError(f"Unsupported payment method: {key}") from None
        if not isinstance(handler, PaymentHandler):
            raise TypeError("Factory builder must return a PaymentHandler.")
        return handler

    @classmethod
    def default(cls):
        factory = cls()
        factory.register("credit_card", CreditCardPayment)
        factory.register("upi", UPIPayment)
        factory.register("paypal", PayPalPayment)
        factory.register("crypto", CryptoPayment)
        return factory
