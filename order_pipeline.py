"""
E-Commerce Order Pipeline
=========================
Design patterns demonstrated
  * Singleton       - ConfigManager and Database (thread-safe, via SingletonMeta)
  * Factory Method  - PaymentHandlerCreator subclasses create CreditCard / UPI /
                      PayPal / Crypto handlers; PaymentFactory picks the creator
  * Observer        - OrderEventBus broadcasts status changes to Logistics,
                      Invoicing and Email listeners (failures are isolated)

Run:  python order_pipeline.py
"""
from __future__ import annotations

import itertools
import logging
import os
import re
import sys
import threading
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Callable, Dict, Iterable, List, Optional, Tuple, Type

log = logging.getLogger("orders")


# ==========================================================================
# Errors
# ==========================================================================
class OrderError(Exception): ...
class ValidationError(OrderError): ...
class PaymentError(OrderError): ...
class UnsupportedPaymentMethod(OrderError): ...
class InvalidTransitionError(OrderError): ...
class OrderNotFound(OrderError): ...


def _money(v) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ==========================================================================
# SINGLETON  (thread-safe, double-checked locking)
# ==========================================================================
class SingletonMeta(type):
    _instances: Dict[type, object] = {}
    _lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        if cls not in SingletonMeta._instances:
            with SingletonMeta._lock:
                if cls not in SingletonMeta._instances:
                    SingletonMeta._instances[cls] = super().__call__(*args, **kwargs)
        return SingletonMeta._instances[cls]

    @staticmethod
    def reset(cls: type) -> None:
        """Drop the instance (test isolation only)."""
        with SingletonMeta._lock:
            SingletonMeta._instances.pop(cls, None)


class ConfigManager(metaclass=SingletonMeta):
    """Single source of truth for settings. Defaults can be overridden with
    environment variables named ORDER_<KEY>, e.g. ORDER_TAX_RATE=0.05"""

    _DEFAULTS = {
        "currency": "INR",
        "tax_rate": "0.18",
        "max_order_value": "500000",
        "enabled_payment_methods": "credit_card,upi,paypal,crypto",
    }

    def __init__(self):
        self.__settings = dict(self._DEFAULTS)
        for key in self._DEFAULTS:
            env = os.environ.get(f"ORDER_{key.upper()}")
            if env:
                self.__settings[key] = env
        self.__lock = threading.RLock()

    def get(self, key: str) -> str:
        with self.__lock:
            try:
                return self.__settings[key]
            except KeyError:
                raise KeyError(f"unknown config key {key!r}")

    def decimal(self, key: str) -> Decimal:
        return Decimal(self.get(key))

    def list(self, key: str) -> List[str]:
        return [v.strip().lower() for v in self.get(key).split(",") if v.strip()]

    def override(self, **values: str) -> None:
        with self.__lock:
            for k, v in values.items():
                if k not in self.__settings:
                    raise KeyError(f"unknown config key {k!r}")
                self.__settings[k] = str(v)


class Database(metaclass=SingletonMeta):
    """In-memory stand-in for a real datastore; one shared connection point."""

    def __init__(self):
        self.__orders: Dict[str, "Order"] = {}
        self.__lock = threading.RLock()
        self.__seq = itertools.count(1)

    def next_order_id(self) -> str:
        with self.__lock:
            return f"ORD-{next(self.__seq):04d}"

    def save(self, order: "Order") -> None:
        with self.__lock:
            self.__orders[order.order_id] = order

    def get(self, order_id: str) -> "Order":
        with self.__lock:
            try:
                return self.__orders[order_id]
            except KeyError:
                raise OrderNotFound(order_id)

    def all(self) -> List["Order"]:
        with self.__lock:
            return list(self.__orders.values())


# ==========================================================================
# Domain: orders and a guarded state machine
# ==========================================================================
class OrderStatus(Enum):
    CREATED = "CREATED"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    PAID = "PAID"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


_ALLOWED: Dict[OrderStatus, set] = {
    OrderStatus.CREATED: {OrderStatus.PAID, OrderStatus.PAYMENT_FAILED, OrderStatus.CANCELLED},
    OrderStatus.PAYMENT_FAILED: {OrderStatus.PAID, OrderStatus.CANCELLED},
    OrderStatus.PAID: {OrderStatus.SHIPPED, OrderStatus.CANCELLED},
    OrderStatus.SHIPPED: {OrderStatus.DELIVERED},
    OrderStatus.DELIVERED: set(),
    OrderStatus.CANCELLED: set(),
}


@dataclass(frozen=True)
class OrderItem:
    sku: str
    name: str
    unit_price: Decimal
    qty: int

    def __post_init__(self):
        if self.qty < 1:
            raise ValidationError("quantity must be at least 1")
        if Decimal(str(self.unit_price)) <= 0:
            raise ValidationError("unit price must be positive")

    @property
    def line_total(self) -> Decimal:
        return _money(Decimal(str(self.unit_price)) * self.qty)


class Order:
    def __init__(self, order_id: str, customer_email: str, items: List[OrderItem],
                 tax_rate: Decimal, currency: str):
        self.order_id = order_id
        self.customer_email = customer_email
        self.items = tuple(items)
        self.currency = currency
        self.subtotal = _money(sum((i.line_total for i in items), Decimal("0")))
        self.tax = _money(self.subtotal * tax_rate)
        self.total = self.subtotal + self.tax
        self.status = OrderStatus.CREATED
        self.payment_ref: Optional[str] = None
        self.history: List[Tuple[OrderStatus, datetime]] = [
            (OrderStatus.CREATED, datetime.now(timezone.utc))]

    def transition(self, new: OrderStatus) -> OrderStatus:
        if new not in _ALLOWED[self.status]:
            raise InvalidTransitionError(
                f"{self.order_id}: {self.status.value} -> {new.value} is not allowed")
        old, self.status = self.status, new
        self.history.append((new, datetime.now(timezone.utc)))
        return old


# ==========================================================================
# FACTORY METHOD  - payment handlers
# ==========================================================================
@dataclass(frozen=True)
class PaymentResult:
    success: bool
    reference: Optional[str]
    message: str


class PaymentHandler(ABC):
    """Product interface."""
    method_name: str = ""

    def pay(self, amount: Decimal, details: Dict[str, str]) -> PaymentResult:
        """Template: validate input, then charge."""
        if amount <= 0:
            raise PaymentError("amount must be positive")
        self.validate(details)
        return self.charge(amount, details)

    @abstractmethod
    def validate(self, details: Dict[str, str]) -> None:
        """Raise PaymentError for malformed details (no status change)."""

    @abstractmethod
    def charge(self, amount: Decimal, details: Dict[str, str]) -> PaymentResult:
        """Talk to the gateway; return a result (declines are not exceptions)."""

    @staticmethod
    def _ref(prefix: str) -> str:
        return f"{prefix}-{uuid.uuid4().hex[:10].upper()}"


def _luhn_ok(number: str) -> bool:
    total, alt = 0, False
    for ch in reversed(number):
        d = int(ch)
        if alt:
            d = d * 2 - 9 if d * 2 > 9 else d * 2
        total += d
        alt = not alt
    return total % 10 == 0


class CreditCardHandler(PaymentHandler):
    method_name = "credit_card"
    DECLINE_TEST_CARD = "4000000000000002"          # simulated gateway decline

    def validate(self, d):
        number = re.sub(r"[ -]", "", d.get("number", ""))
        if not (number.isdigit() and 13 <= len(number) <= 19 and _luhn_ok(number)):
            raise PaymentError("invalid card number")
        if not re.fullmatch(r"(0[1-9]|1[0-2])/\d{2}", d.get("expiry", "")):
            raise PaymentError("expiry must be MM/YY")
        if not re.fullmatch(r"\d{3,4}", d.get("cvv", "")):
            raise PaymentError("invalid CVV")

    def charge(self, amount, d):
        number = re.sub(r"[ -]", "", d["number"])
        if number == self.DECLINE_TEST_CARD:
            return PaymentResult(False, None, "card declined by issuer")
        return PaymentResult(True, self._ref("CC"), f"card ****{number[-4:]} charged")


class UpiHandler(PaymentHandler):
    method_name = "upi"

    def validate(self, d):
        if not re.fullmatch(r"[\w.\-]{2,}@[A-Za-z]{2,}", d.get("vpa", "")):
            raise PaymentError("invalid UPI ID (expected name@bank)")

    def charge(self, amount, d):
        return PaymentResult(True, self._ref("UPI"), f"collect request approved by {d['vpa']}")


class PayPalHandler(PaymentHandler):
    method_name = "paypal"

    def validate(self, d):
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", d.get("email", "")):
            raise PaymentError("invalid PayPal email")

    def charge(self, amount, d):
        return PaymentResult(True, self._ref("PP"), f"PayPal payment from {d['email']}")


class CryptoHandler(PaymentHandler):
    method_name = "crypto"

    def validate(self, d):
        if not re.fullmatch(r"0x[0-9a-fA-F]{40}", d.get("wallet", "")):
            raise PaymentError("invalid wallet address (expected 0x + 40 hex chars)")

    def charge(self, amount, d):
        w = d["wallet"]
        return PaymentResult(True, self._ref("CRY"), f"transfer from {w[:6]}…{w[-4:]} confirmed")


class PaymentHandlerCreator(ABC):
    """Creator: declares the factory method; subclasses decide the product."""

    @abstractmethod
    def create_handler(self) -> PaymentHandler: ...

    def process(self, amount: Decimal, details: Dict[str, str]) -> PaymentResult:
        return self.create_handler().pay(amount, details)


class CreditCardCreator(PaymentHandlerCreator):
    def create_handler(self): return CreditCardHandler()

class UpiCreator(PaymentHandlerCreator):
    def create_handler(self): return UpiHandler()

class PayPalCreator(PaymentHandlerCreator):
    def create_handler(self): return PayPalHandler()

class CryptoCreator(PaymentHandlerCreator):
    def create_handler(self): return CryptoHandler()


class PaymentFactory:
    """Resolves a method name to its creator. Honours ConfigManager's list of
    enabled methods, and new methods can be registered without edits here."""

    _registry: Dict[str, Type[PaymentHandlerCreator]] = {
        "credit_card": CreditCardCreator,
        "upi": UpiCreator,
        "paypal": PayPalCreator,
        "crypto": CryptoCreator,
    }

    @classmethod
    def register(cls, method: str, creator: Type[PaymentHandlerCreator]) -> None:
        cls._registry[method.lower()] = creator

    @classmethod
    def get_creator(cls, method: str) -> PaymentHandlerCreator:
        key = (method or "").strip().lower()
        if key not in cls._registry:
            raise UnsupportedPaymentMethod(f"unknown payment method {method!r}")
        if key not in ConfigManager().list("enabled_payment_methods"):
            raise UnsupportedPaymentMethod(f"payment method {key!r} is disabled")
        return cls._registry[key]()


# ==========================================================================
# OBSERVER  - order status events
# ==========================================================================
@dataclass(frozen=True)
class OrderEvent:
    order: Order
    old_status: Optional[OrderStatus]
    new_status: OrderStatus
    timestamp: datetime


class OrderObserver(ABC):
    @abstractmethod
    def on_event(self, event: OrderEvent) -> None: ...


class OrderEventBus:
    """Subject. Observers may subscribe to specific statuses or to all."""

    def __init__(self):
        self.__subs: List[Tuple[OrderObserver, Optional[frozenset]]] = []
        self.__lock = threading.RLock()

    def subscribe(self, observer: OrderObserver,
                  statuses: Optional[Iterable[OrderStatus]] = None) -> None:
        with self.__lock:
            self.__subs.append((observer, frozenset(statuses) if statuses else None))

    def unsubscribe(self, observer: OrderObserver) -> None:
        with self.__lock:
            self.__subs = [(o, s) for o, s in self.__subs if o is not observer]

    def publish(self, event: OrderEvent) -> int:
        """Notify interested observers; one failing observer never blocks the
        rest. Returns the number of observer failures."""
        with self.__lock:
            targets = [o for o, s in self.__subs if s is None or event.new_status in s]
        failures = 0
        for obs in targets:
            try:
                obs.on_event(event)
            except Exception:
                failures += 1
                log.warning("observer %s failed on %s", type(obs).__name__,
                            event.order.order_id, exc_info=False)
        return failures


class LogisticsListener(OrderObserver):
    def __init__(self):
        self.shipments: Dict[str, str] = {}

    def on_event(self, e):
        o = e.order
        if e.new_status is OrderStatus.PAID:
            self.shipments[o.order_id] = f"TRK{uuid.uuid4().hex[:8].upper()}"
            log.info("  [logistics] shipment %s booked for %s", self.shipments[o.order_id], o.order_id)
        elif e.new_status is OrderStatus.CANCELLED and o.order_id in self.shipments:
            log.info("  [logistics] shipment %s cancelled", self.shipments.pop(o.order_id))


class InvoicingListener(OrderObserver):
    def __init__(self):
        self.invoices: Dict[str, str] = {}
        self.credit_notes: List[str] = []
        self._seq = itertools.count(1)

    def on_event(self, e):
        o = e.order
        if e.new_status is OrderStatus.PAID:
            self.invoices[o.order_id] = f"INV-{next(self._seq):05d}"
            log.info("  [invoicing] %s issued for %s (%s %s)", self.invoices[o.order_id],
                     o.order_id, o.total, o.currency)
        elif e.new_status is OrderStatus.CANCELLED and o.order_id in self.invoices:
            self.credit_notes.append(f"CN-{self.invoices[o.order_id][4:]}")
            log.info("  [invoicing] credit note %s issued", self.credit_notes[-1])


class EmailListener(OrderObserver):
    _TEMPLATES = {
        OrderStatus.CREATED: "We received your order {id}.",
        OrderStatus.PAYMENT_FAILED: "Payment for {id} failed. Please try another method.",
        OrderStatus.PAID: "Payment received for {id}. Total {total} {cur}.",
        OrderStatus.SHIPPED: "Your order {id} is on its way.",
        OrderStatus.DELIVERED: "Your order {id} was delivered. Thank you!",
        OrderStatus.CANCELLED: "Your order {id} was cancelled.",
    }

    def __init__(self):
        self.sent: List[Tuple[str, str]] = []

    def on_event(self, e):
        o = e.order
        body = self._TEMPLATES[e.new_status].format(id=o.order_id, total=o.total, cur=o.currency)
        self.sent.append((o.customer_email, body))
        log.info("  [email] to %s: %s", o.customer_email, body)


# ==========================================================================
# Service: orchestrates the pipeline
# ==========================================================================
class OrderService:
    def __init__(self, bus: OrderEventBus, db: Optional[Database] = None,
                 config: Optional[ConfigManager] = None):
        self._bus = bus
        self._db = db or Database()
        self._cfg = config or ConfigManager()

    def create_order(self, customer_email: str, items: List[OrderItem]) -> Order:
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", customer_email or ""):
            raise ValidationError("invalid customer email")
        if not items:
            raise ValidationError("order needs at least one item")
        order = Order(self._db.next_order_id(), customer_email, list(items),
                      self._cfg.decimal("tax_rate"), self._cfg.get("currency"))
        if order.total > self._cfg.decimal("max_order_value"):
            raise ValidationError(f"order total {order.total} exceeds the allowed maximum")
        self._db.save(order)
        self._publish(order, None, OrderStatus.CREATED)
        return order

    def pay(self, order_id: str, method: str, details: Dict[str, str]) -> PaymentResult:
        order = self._db.get(order_id)
        if order.status not in (OrderStatus.CREATED, OrderStatus.PAYMENT_FAILED):
            raise InvalidTransitionError(f"{order_id} cannot be paid while {order.status.value}")
        creator = PaymentFactory.get_creator(method)          # Factory Method
        result = creator.process(order.total, details)
        if result.success:
            order.payment_ref = result.reference
            self._move(order, OrderStatus.PAID)
        else:
            self._move(order, OrderStatus.PAYMENT_FAILED)
        return result

    def ship(self, order_id): return self._move(self._db.get(order_id), OrderStatus.SHIPPED)
    def deliver(self, order_id): return self._move(self._db.get(order_id), OrderStatus.DELIVERED)
    def cancel(self, order_id): return self._move(self._db.get(order_id), OrderStatus.CANCELLED)

    def _move(self, order: Order, new: OrderStatus) -> Order:
        old = order.transition(new)
        self._db.save(order)
        self._publish(order, old, new)
        return order

    def _publish(self, order, old, new):
        self._bus.publish(OrderEvent(order, old, new, datetime.now(timezone.utc)))


# ==========================================================================
# Tests
# ==========================================================================
def _fresh_env():
    SingletonMeta.reset(ConfigManager)
    SingletonMeta.reset(Database)


def _tests():
    # ---- Singleton -------------------------------------------------------
    _fresh_env()
    assert ConfigManager() is ConfigManager() and Database() is Database()
    ids, barrier = [], threading.Barrier(20)

    def grab():
        barrier.wait()
        ids.append(id(Database()))
    ts = [threading.Thread(target=grab) for _ in range(20)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert len(set(ids)) == 1, "singleton must survive concurrent first access"

    # ---- Factory Method --------------------------------------------------
    expected = {"credit_card": CreditCardHandler, "UPI": UpiHandler,
                "paypal": PayPalHandler, "crypto": CryptoHandler}
    for name, cls in expected.items():
        assert isinstance(PaymentFactory.get_creator(name).create_handler(), cls)
    try:
        PaymentFactory.get_creator("barter"); raise AssertionError
    except UnsupportedPaymentMethod:
        pass
    ConfigManager().override(enabled_payment_methods="upi")
    try:
        PaymentFactory.get_creator("crypto"); raise AssertionError
    except UnsupportedPaymentMethod:
        pass
    _fresh_env()

    # extension without editing the factory class body
    class CashCreator(PaymentHandlerCreator):
        def create_handler(self):
            class Cash(PaymentHandler):
                def validate(self, d): pass
                def charge(self, a, d): return PaymentResult(True, "CASH-1", "cash")
            return Cash()
    PaymentFactory.register("cash", CashCreator)
    ConfigManager().override(enabled_payment_methods="cash,upi,credit_card,paypal,crypto")
    assert PaymentFactory.get_creator("cash").process(Decimal("5"), {}).success
    _fresh_env()

    # ---- Handler validation ---------------------------------------------
    cc = CreditCardHandler()
    assert cc.pay(Decimal("10"), {"number": "4111 1111 1111 1111", "expiry": "12/30", "cvv": "123"}).success
    assert not cc.pay(Decimal("10"), {"number": CreditCardHandler.DECLINE_TEST_CARD,
                                      "expiry": "12/30", "cvv": "123"}).success
    for bad in ({"number": "1234567812345678", "expiry": "12/30", "cvv": "123"},
                {"number": "4111111111111111", "expiry": "13/30", "cvv": "123"}):
        try:
            cc.pay(Decimal("10"), bad); raise AssertionError
        except PaymentError:
            pass

    # ---- Observer + pipeline --------------------------------------------
    bus = OrderEventBus()
    logi, inv, mail = LogisticsListener(), InvoicingListener(), EmailListener()
    bus.subscribe(logi, [OrderStatus.PAID, OrderStatus.CANCELLED])
    bus.subscribe(inv, [OrderStatus.PAID, OrderStatus.CANCELLED])
    bus.subscribe(mail)

    class Broken(OrderObserver):
        def on_event(self, e): raise RuntimeError("boom")
    bus.subscribe(Broken())

    svc = OrderService(bus)
    item = OrderItem("SKU1", "Keyboard", Decimal("1000"), 2)
    o = svc.create_order("a@x.com", [item])
    assert (o.subtotal, o.tax, o.total) == (Decimal("2000.00"), Decimal("360.00"), Decimal("2360.00"))
    assert len(mail.sent) == 1 and not logi.shipments          # CREATED -> email only

    r = svc.pay(o.order_id, "credit_card", {"number": CreditCardHandler.DECLINE_TEST_CARD,
                                            "expiry": "12/30", "cvv": "123"})
    assert not r.success and o.status is OrderStatus.PAYMENT_FAILED and not logi.shipments
    svc.pay(o.order_id, "upi", {"vpa": "asha@okbank"})           # retry succeeds
    assert o.status is OrderStatus.PAID and o.order_id in logi.shipments and o.order_id in inv.invoices
    svc.ship(o.order_id); svc.deliver(o.order_id)
    assert o.status is OrderStatus.DELIVERED and len(mail.sent) == 5

    for bad_call in (lambda: svc.cancel(o.order_id),
                     lambda: svc.pay(o.order_id, "upi", {"vpa": "a@b"})):
        try:
            bad_call(); raise AssertionError
        except InvalidTransitionError:
            pass

    # cancel after payment -> logistics + invoicing react
    o2 = svc.create_order("b@x.com", [item])
    svc.pay(o2.order_id, "paypal", {"email": "b@x.com"})
    svc.cancel(o2.order_id)
    assert o2.order_id not in logi.shipments and len(inv.credit_notes) == 1

    # bad payment details leave state untouched
    o3 = svc.create_order("c@x.com", [item])
    try:
        svc.pay(o3.order_id, "crypto", {"wallet": "nope"}); raise AssertionError
    except PaymentError:
        assert o3.status is OrderStatus.CREATED

    # unsubscribe stops delivery
    before = len(mail.sent)
    bus.unsubscribe(mail)
    svc.cancel(o3.order_id)
    assert len(mail.sent) == before

    # create-order validation
    for args in (("bad", [item]), ("a@x.com", []),
                 ("a@x.com", [OrderItem("S", "Big", Decimal("600000"), 1)])):
        try:
            svc.create_order(*args); raise AssertionError
        except ValidationError:
            pass
    _fresh_env()
    print("All self-tests passed.\n")


# ==========================================================================
# Demo
# ==========================================================================
def _demo():
    cfg, db = ConfigManager(), Database()
    print(f"Singletons shared: config={cfg is ConfigManager()}, db={db is Database()}\n")

    bus = OrderEventBus()
    logistics, invoicing, email = LogisticsListener(), InvoicingListener(), EmailListener()
    bus.subscribe(logistics, [OrderStatus.PAID, OrderStatus.CANCELLED])
    bus.subscribe(invoicing, [OrderStatus.PAID, OrderStatus.CANCELLED])
    bus.subscribe(email)
    svc = OrderService(bus)

    laptop = OrderItem("LAP-1", "Laptop", Decimal("55000"), 1)
    mouse = OrderItem("MOU-7", "Wireless Mouse", Decimal("799.50"), 2)

    print("--- Order 1: UPI, full lifecycle ---")
    o1 = svc.create_order("asha@example.com", [laptop, mouse])
    svc.pay(o1.order_id, "upi", {"vpa": "asha@okbank"})
    svc.ship(o1.order_id)
    svc.deliver(o1.order_id)

    print("\n--- Order 2: card declined, retry with PayPal ---")
    o2 = svc.create_order("ravi@example.com", [mouse])
    svc.pay(o2.order_id, "credit_card", {"number": CreditCardHandler.DECLINE_TEST_CARD,
                                         "expiry": "09/29", "cvv": "321"})
    svc.pay(o2.order_id, "paypal", {"email": "ravi@example.com"})

    print("\n--- Order 3: paid with crypto, then cancelled ---")
    o3 = svc.create_order("meera@example.com", [laptop])
    svc.pay(o3.order_id, "crypto", {"wallet": "0x" + "ab12" * 10})
    svc.cancel(o3.order_id)

    print("\n--- Guard rails ---")
    for label, fn in (("ship a cancelled order", lambda: svc.ship(o3.order_id)),
                      ("pay an already-paid order", lambda: svc.pay(o2.order_id, "upi", {"vpa": "ravi@okbank"}))):
        try:
            fn()
        except OrderError as exc:
            print(f"  blocked ({label}): {exc}")

    print("\n--- Summary ---")
    for o in db.all():
        print(f"  {o.order_id}  {o.status.value:<14} {o.total:>10} {o.currency}  "
              f"pay_ref={o.payment_ref}  invoice={invoicing.invoices.get(o.order_id, '-')}")
    print(f"  emails sent: {len(email.sent)}, credit notes: {len(invoicing.credit_notes)}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
    logging.disable(logging.CRITICAL)          # keep test output quiet
    _tests()
    logging.disable(logging.NOTSET)
    _demo()
